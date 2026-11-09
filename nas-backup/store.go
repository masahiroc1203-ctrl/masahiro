package main

// バックアップ先ディレクトリへの保存処理。
//
// ディレクトリ構成:
//   <root>/<保存先フォルダ名>/<YYYY>/<YYYY-MM>/<ファイル名>   (layout=date)
//   <root>/<保存先フォルダ名>/<ファイル名>                    (layout=flat)
//   <root>/.nasbackup/index.jsonl     バックアップ済みファイルの一覧
//   <root>/.nasbackup/tmp/<id>.part   受信途中のファイル (再開用)
//   <root>/.nasbackup/tmp/<id>.json   受信途中のファイル情報

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

const (
	stateDirName = ".nasbackup"
	staleAfter   = 7 * 24 * time.Hour
)

var (
	ErrNotFound      = errors.New("upload session not found")
	ErrOffset        = errors.New("offset mismatch")
	ErrTooLarge      = errors.New("data exceeds declared file size")
	ErrInvalidName   = errors.New("invalid file name")
	ErrInvalidOwner  = errors.New("invalid folder name")
	ErrInvalidSize   = errors.New("invalid file size")
	ErrInvalidLayout = errors.New("layout must be \"date\" or \"flat\"")
)

// FileInfo はクライアントから送られるファイル情報。
type FileInfo struct {
	Name         string `json:"name"`
	Size         int64  `json:"size"`
	LastModified int64  `json:"lastModified"` // UNIX ミリ秒 (ブラウザの File.lastModified)
	Owner        string `json:"owner"`
}

type session struct {
	FileInfo
	ID      string    `json:"id"`
	Created time.Time `json:"created"`
}

type indexEntry struct {
	Owner string    `json:"owner"`
	Name  string    `json:"name"`
	Size  int64     `json:"size"`
	Path  string    `json:"path"` // root からの相対パス (区切りは /)
	At    time.Time `json:"at"`
}

// UploadResult はアップロード処理の結果。
type UploadResult struct {
	Status string `json:"status"` // pending / done / exists
	ID     string `json:"id,omitempty"`
	Offset int64  `json:"offset"`
	Path   string `json:"path,omitempty"`
}

type Store struct {
	root   string
	tmpDir string
	layout string

	mu     sync.Mutex // index と確定処理を保護
	index  map[string]indexEntry
	indexF *os.File

	locksMu sync.Mutex
	locks   map[string]*sync.Mutex
}

func NewStore(root, layout string) (*Store, error) {
	if layout != "date" && layout != "flat" {
		return nil, ErrInvalidLayout
	}
	root, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	s := &Store{
		root:   root,
		tmpDir: filepath.Join(root, stateDirName, "tmp"),
		layout: layout,
		index:  map[string]indexEntry{},
		locks:  map[string]*sync.Mutex{},
	}
	if err := os.MkdirAll(s.tmpDir, 0o755); err != nil {
		return nil, err
	}
	indexPath := filepath.Join(root, stateDirName, "index.jsonl")
	if err := s.loadIndex(indexPath); err != nil {
		return nil, err
	}
	s.indexF, err = os.OpenFile(indexPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return nil, err
	}
	return s, nil
}

func (s *Store) Close() error { return s.indexF.Close() }

func (s *Store) Root() string { return s.root }

func (s *Store) loadIndex(p string) error {
	f, err := os.Open(p)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 64*1024), 1<<20)
	for sc.Scan() {
		var e indexEntry
		if json.Unmarshal(sc.Bytes(), &e) == nil && e.Path != "" {
			s.index[indexKey(e.Owner, e.Name, e.Size)] = e
		}
	}
	return sc.Err()
}

func indexKey(owner, name string, size int64) string {
	return fmt.Sprintf("%s\x00%s\x00%d", owner, name, size)
}

func sessionID(owner, name string, size int64) string {
	h := sha256.Sum256([]byte(indexKey(owner, name, size)))
	return hex.EncodeToString(h[:16])
}

func validID(id string) bool {
	if len(id) != 32 {
		return false
	}
	_, err := hex.DecodeString(id)
	return err == nil
}

func (s *Store) lock(id string) func() {
	s.locksMu.Lock()
	m, ok := s.locks[id]
	if !ok {
		m = &sync.Mutex{}
		s.locks[id] = m
	}
	s.locksMu.Unlock()
	m.Lock()
	return m.Unlock
}

func (s *Store) normalize(fi FileInfo) (FileInfo, error) {
	name, err := sanitizeName(fi.Name, 200)
	if err != nil {
		return fi, ErrInvalidName
	}
	fi.Name = name
	if strings.TrimSpace(fi.Owner) != "" {
		owner, err := sanitizeName(fi.Owner, 64)
		if err != nil {
			return fi, ErrInvalidOwner
		}
		fi.Owner = owner
	} else {
		fi.Owner = ""
	}
	if fi.Size < 0 {
		return fi, ErrInvalidSize
	}
	return fi, nil
}

// Exists はバックアップ済みかどうかを返す (index に記録があり、実ファイルも残っている場合)。
func (s *Store) Exists(fi FileInfo) (string, bool) {
	fi, err := s.normalize(fi)
	if err != nil {
		return "", false
	}
	s.mu.Lock()
	e, ok := s.index[indexKey(fi.Owner, fi.Name, fi.Size)]
	s.mu.Unlock()
	if !ok {
		return "", false
	}
	st, err := os.Stat(filepath.Join(s.root, filepath.FromSlash(e.Path)))
	if err != nil || !st.Mode().IsRegular() || st.Size() != fi.Size {
		return "", false
	}
	return e.Path, true
}

// Begin はアップロードを開始 (または中断したところから再開) する。
func (s *Store) Begin(fi FileInfo) (UploadResult, error) {
	fi, err := s.normalize(fi)
	if err != nil {
		return UploadResult{}, err
	}
	if p, ok := s.Exists(fi); ok {
		return UploadResult{Status: "exists", Offset: fi.Size, Path: p}, nil
	}
	id := sessionID(fi.Owner, fi.Name, fi.Size)
	unlock := s.lock(id)
	defer unlock()
	// ロック待ちの間に別のリクエストが保存を終えている場合がある
	if p, ok := s.Exists(fi); ok {
		return UploadResult{Status: "exists", Offset: fi.Size, Path: p}, nil
	}

	metaPath, partPath := s.sessionPaths(id)
	if _, err := os.Stat(metaPath); errors.Is(err, os.ErrNotExist) {
		sess := session{FileInfo: fi, ID: id, Created: time.Now()}
		b, _ := json.Marshal(sess)
		if err := os.WriteFile(metaPath, b, 0o644); err != nil {
			return UploadResult{}, err
		}
	}
	f, err := os.OpenFile(partPath, os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return UploadResult{}, err
	}
	st, err := f.Stat()
	f.Close()
	if err != nil {
		return UploadResult{}, err
	}
	offset := st.Size()
	if offset > fi.Size { // 想定外: 作り直す
		if err := os.Truncate(partPath, 0); err != nil {
			return UploadResult{}, err
		}
		offset = 0
	}
	// 前回の通信で最後まで届いていたが確定前に切断された場合
	if offset == fi.Size && fi.Size > 0 {
		sess, err := s.loadSession(id)
		if err != nil {
			return UploadResult{}, err
		}
		p, err := s.finalize(sess)
		if err != nil {
			return UploadResult{}, err
		}
		return UploadResult{Status: "done", ID: id, Offset: fi.Size, Path: p}, nil
	}
	return UploadResult{Status: "pending", ID: id, Offset: offset}, nil
}

// Write は offset の位置からデータを書き込む。ファイルが揃ったら保存先へ移動する。
func (s *Store) Write(id string, offset int64, r io.Reader) (UploadResult, error) {
	if !validID(id) {
		return UploadResult{}, ErrNotFound
	}
	unlock := s.lock(id)
	defer unlock()

	sess, err := s.loadSession(id)
	if err != nil {
		return UploadResult{}, err
	}
	_, partPath := s.sessionPaths(id)
	f, err := os.OpenFile(partPath, os.O_WRONLY, 0o644)
	if errors.Is(err, os.ErrNotExist) {
		return UploadResult{}, ErrNotFound
	}
	if err != nil {
		return UploadResult{}, err
	}
	st, err := f.Stat()
	if err != nil {
		f.Close()
		return UploadResult{}, err
	}
	cur := st.Size()
	if offset != cur {
		f.Close()
		return UploadResult{Status: "pending", ID: id, Offset: cur}, ErrOffset
	}
	if _, err := f.Seek(cur, io.SeekStart); err != nil {
		f.Close()
		return UploadResult{}, err
	}
	remaining := sess.Size - cur
	n, copyErr := io.Copy(f, io.LimitReader(r, remaining+1))
	if n > remaining {
		f.Truncate(cur)
		f.Close()
		return UploadResult{Status: "pending", ID: id, Offset: cur}, ErrTooLarge
	}
	if err := f.Close(); err != nil {
		return UploadResult{}, err
	}
	cur += n
	if copyErr != nil {
		// 途中まで届いた分は残す。クライアントは offset を確認して続きから送る。
		return UploadResult{Status: "pending", ID: id, Offset: cur}, copyErr
	}
	if cur < sess.Size {
		return UploadResult{Status: "pending", ID: id, Offset: cur}, nil
	}
	p, err := s.finalize(sess)
	if err != nil {
		return UploadResult{}, err
	}
	return UploadResult{Status: "done", ID: id, Offset: cur, Path: p}, nil
}

func (s *Store) sessionPaths(id string) (meta, part string) {
	return filepath.Join(s.tmpDir, id+".json"), filepath.Join(s.tmpDir, id+".part")
}

func (s *Store) loadSession(id string) (session, error) {
	metaPath, _ := s.sessionPaths(id)
	b, err := os.ReadFile(metaPath)
	if errors.Is(err, os.ErrNotExist) {
		return session{}, ErrNotFound
	}
	if err != nil {
		return session{}, err
	}
	var sess session
	if err := json.Unmarshal(b, &sess); err != nil {
		return session{}, err
	}
	return sess, nil
}

// finalize は受信済みファイルを保存先へ移動し、index に記録する。
func (s *Store) finalize(sess session) (string, error) {
	metaPath, partPath := s.sessionPaths(sess.ID)

	f, err := os.OpenFile(partPath, os.O_RDWR, 0)
	if err != nil {
		return "", err
	}
	if err := f.Sync(); err != nil {
		f.Close()
		return "", err
	}
	taken, ok := CaptureTime(f)
	f.Close()
	if !ok {
		taken = fallbackTime(sess.LastModified)
	}

	relDir := s.relDir(sess.Owner, taken)
	dir := filepath.Join(s.root, filepath.FromSlash(relDir))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	ext := path.Ext(sess.Name)
	base := strings.TrimSuffix(sess.Name, ext)
	var rel string
	for i := 0; ; i++ {
		name := sess.Name
		if i > 0 {
			name = fmt.Sprintf("%s (%d)%s", base, i, ext)
		}
		dest := filepath.Join(dir, name)
		rel = path.Join(relDir, name)
		st, err := os.Lstat(dest)
		if errors.Is(err, os.ErrNotExist) {
			if err := moveFile(partPath, dest); err != nil {
				return "", err
			}
			os.Chtimes(dest, taken, taken)
			break
		}
		if err != nil {
			return "", err
		}
		// 同名ファイルがすでにあり、中身も同じなら重複として扱う
		if st.Mode().IsRegular() && st.Size() == sess.Size {
			same, err := sameContent(partPath, dest)
			if err != nil {
				return "", err
			}
			if same {
				os.Remove(partPath)
				break
			}
		}
		if i > 9999 {
			return "", errors.New("too many files with the same name")
		}
	}
	os.Remove(metaPath)

	e := indexEntry{Owner: sess.Owner, Name: sess.Name, Size: sess.Size, Path: rel, At: time.Now()}
	s.index[indexKey(e.Owner, e.Name, e.Size)] = e
	line, _ := json.Marshal(e)
	if _, err := s.indexF.Write(append(line, '\n')); err != nil {
		log.Printf("index write error: %v", err)
	}
	log.Printf("saved %s (%s)", rel, humanBytes(sess.Size))
	return rel, nil
}

func (s *Store) relDir(owner string, t time.Time) string {
	var parts []string
	if owner != "" {
		parts = append(parts, owner)
	}
	if s.layout == "date" {
		parts = append(parts, t.Format("2006"), t.Format("2006-01"))
	}
	if len(parts) == 0 {
		return "."
	}
	return path.Join(parts...)
}

func fallbackTime(lastModifiedMs int64) time.Time {
	if lastModifiedMs > 0 {
		t := time.UnixMilli(lastModifiedMs)
		if plausible(t) {
			return t
		}
	}
	return time.Now()
}

// CleanupStale は長期間更新されていない受信途中のファイルを削除する。
func (s *Store) CleanupStale(maxAge time.Duration) {
	entries, err := os.ReadDir(s.tmpDir)
	if err != nil {
		return
	}
	cutoff := time.Now().Add(-maxAge)
	for _, e := range entries {
		name := e.Name()
		if !strings.HasSuffix(name, ".part") {
			continue
		}
		info, err := e.Info()
		if err != nil || info.ModTime().After(cutoff) {
			continue
		}
		id := strings.TrimSuffix(name, ".part")
		unlock := s.lock(id)
		meta, part := s.sessionPaths(id)
		os.Remove(part)
		os.Remove(meta)
		unlock()
		log.Printf("removed stale partial upload %s", id)
	}
}

func moveFile(src, dst string) error {
	if err := os.Link(src, dst); err == nil {
		// Link は宛先が存在すると失敗するので上書き事故が起きない
		return os.Remove(src)
	}
	if err := os.Rename(src, dst); err == nil {
		return nil
	}
	// 別ファイルシステム等で rename できない場合はコピー
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		os.Remove(dst)
		return err
	}
	if err := out.Close(); err != nil {
		os.Remove(dst)
		return err
	}
	return os.Remove(src)
}

func sameContent(a, b string) (bool, error) {
	fa, err := os.Open(a)
	if err != nil {
		return false, err
	}
	defer fa.Close()
	fb, err := os.Open(b)
	if err != nil {
		return false, err
	}
	defer fb.Close()
	ba := make([]byte, 1<<20)
	bb := make([]byte, 1<<20)
	for {
		na, ea := io.ReadFull(fa, ba)
		nb, eb := io.ReadFull(fb, bb)
		if na != nb || !bytes.Equal(ba[:na], bb[:nb]) {
			return false, nil
		}
		if ea == io.EOF || ea == io.ErrUnexpectedEOF {
			return eb == io.EOF || eb == io.ErrUnexpectedEOF, nil
		}
		if ea != nil {
			return false, ea
		}
		if eb != nil {
			return false, eb
		}
	}
}

// sanitizeName はファイル名・フォルダ名として安全な文字列にする。
// パス区切りや制御文字を取り除き、".." などによるディレクトリ外への書き込みを防ぐ。
func sanitizeName(name string, maxBytes int) (string, error) {
	name = strings.ReplaceAll(name, "\\", "/")
	if i := strings.LastIndex(name, "/"); i >= 0 {
		name = name[i+1:]
	}
	name = strings.Map(func(r rune) rune {
		switch {
		case r < 0x20 || r == 0x7f || r == utf8.RuneError:
			return -1
		case strings.ContainsRune(`:*?"<>|`, r):
			return '_'
		}
		return r
	}, name)
	name = strings.TrimRight(name, ". ")
	name = strings.TrimLeft(name, ". ") // 隠しファイルや .nasbackup との衝突を避ける
	if name == "" {
		return "", ErrInvalidName
	}
	if len(name) > maxBytes {
		ext := path.Ext(name)
		if len(ext) > 16 {
			ext = ""
		}
		base := strings.TrimSuffix(name, ext)
		for len(base)+len(ext) > maxBytes {
			_, size := utf8.DecodeLastRuneInString(base)
			base = base[:len(base)-size]
		}
		name = base + ext
	}
	return name, nil
}

func humanBytes(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div, exp := int64(unit), 0
	for m := n / unit; m >= unit; m /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(n)/float64(div), "KMGTPE"[exp])
}
