package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"
	"time"
)

type testEnv struct {
	t     *testing.T
	root  string
	store *Store
	srv   *httptest.Server
}

func newEnv(t *testing.T, password string) *testEnv {
	t.Helper()
	root := t.TempDir()
	store, err := NewStore(root, "date")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { store.Close() })
	static := fstest.MapFS{"index.html": {Data: []byte("<html>ok</html>")}}
	srv := httptest.NewServer(NewServer(store, password, static))
	t.Cleanup(srv.Close)
	return &testEnv{t: t, root: root, store: store, srv: srv}
}

func (e *testEnv) do(method, path string, body io.Reader, hdr map[string]string) (int, map[string]any) {
	e.t.Helper()
	req, _ := http.NewRequest(method, e.srv.URL+path, body)
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	defer res.Body.Close()
	var m map[string]any
	json.NewDecoder(res.Body).Decode(&m)
	return res.StatusCode, m
}

func (e *testEnv) begin(fi FileInfo) map[string]any {
	e.t.Helper()
	b, _ := json.Marshal(fi)
	code, m := e.do("POST", "/api/uploads", bytes.NewReader(b), nil)
	if code != 200 {
		e.t.Fatalf("begin: %d %v", code, m)
	}
	return m
}

func (e *testEnv) put(id string, offset int, data []byte) (int, map[string]any) {
	e.t.Helper()
	return e.do("PUT", "/api/uploads/"+id, bytes.NewReader(data), map[string]string{"Upload-Offset": fmt.Sprint(offset)})
}

// upload は chunk バイトずつに分けてファイルを送る。
func (e *testEnv) upload(fi FileInfo, data []byte, chunk int) map[string]any {
	e.t.Helper()
	m := e.begin(fi)
	if m["status"] != "pending" {
		return m
	}
	id := m["id"].(string)
	off := int(m["offset"].(float64))
	for {
		end := min(off+chunk, len(data))
		code, r := e.put(id, off, data[off:end])
		if code != 200 {
			e.t.Fatalf("put: %d %v", code, r)
		}
		if r["status"] == "done" {
			return r
		}
		off = int(r["offset"].(float64))
	}
}

func readFixture(t *testing.T, name string) []byte {
	b, err := os.ReadFile(name)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestUploadInChunksSortedByCaptureDate(t *testing.T) {
	e := newEnv(t, "")
	data := readFixture(t, "testdata/exif.jpg")
	r := e.upload(FileInfo{Name: "IMG_0001.JPG", Size: int64(len(data)), Owner: "papa"}, data, 100)

	want := "papa/2024/2024-05/IMG_0001.JPG"
	if r["path"] != want {
		t.Fatalf("path = %v, want %v", r["path"], want)
	}
	got, err := os.ReadFile(filepath.Join(e.root, want))
	if err != nil || !bytes.Equal(got, data) {
		t.Fatalf("saved file differs: %v", err)
	}
	// ファイルの更新日時が撮影日時になっていること
	st, _ := os.Stat(filepath.Join(e.root, want))
	if !st.ModTime().Equal(time.Date(2024, 5, 3, 5, 15, 16, 0, time.UTC)) {
		t.Errorf("mtime = %v", st.ModTime())
	}
	// 一時ファイルが残っていないこと
	if left, _ := os.ReadDir(filepath.Join(e.root, stateDirName, "tmp")); len(left) != 0 {
		t.Errorf("tmp not cleaned: %d files", len(left))
	}
}

func TestVideoAndFallbackDates(t *testing.T) {
	e := newEnv(t, "")
	video := readFixture(t, "testdata/video.mp4")
	r := e.upload(FileInfo{Name: "VID.mp4", Size: int64(len(video))}, video, 1<<20)
	// mvhd の UTC 時刻をローカル時刻に変換してフォルダを決める
	local := time.Date(2023, 8, 10, 1, 2, 3, 0, time.UTC).In(time.Local)
	if want := local.Format("2006/2006-01") + "/VID.mp4"; r["path"] != want {
		t.Fatalf("video path = %v, want %v", r["path"], want)
	}

	// メタデータが無い場合はブラウザの lastModified を使う
	plain := []byte("not really a photo")
	lm := time.Date(2018, 3, 20, 12, 0, 0, 0, time.Local)
	r = e.upload(FileInfo{Name: "scan.png", Size: int64(len(plain)), LastModified: lm.UnixMilli()}, plain, 4)
	if r["path"] != "2018/2018-03/scan.png" {
		t.Fatalf("fallback path = %v", r["path"])
	}
}

func TestDuplicateIsSkipped(t *testing.T) {
	e := newEnv(t, "")
	data := readFixture(t, "testdata/exif.jpg")
	fi := FileInfo{Name: "IMG_0001.JPG", Size: int64(len(data))}
	e.upload(fi, data, 1<<20)

	m := e.begin(fi)
	if m["status"] != "exists" || m["path"] != "2024/2024-05/IMG_0001.JPG" {
		t.Fatalf("second begin = %v", m)
	}

	// /api/check でも確認できる
	body := `{"owner":"","files":[{"name":"IMG_0001.JPG","size":` + fmt.Sprint(len(data)) + `},{"name":"IMG_0002.JPG","size":10}]}`
	code, c := e.do("POST", "/api/check", strings.NewReader(body), nil)
	files := c["files"].([]any)
	if code != 200 || files[0].(map[string]any)["exists"] != true || files[1].(map[string]any)["exists"] != false {
		t.Fatalf("check = %d %v", code, c)
	}

	// 保存先フォルダ名が違えば別扱い
	fi.Owner = "mama"
	if m := e.begin(fi); m["status"] != "pending" {
		t.Fatalf("other owner = %v", m)
	}

	// NAS 上のファイルを消したら、もう一度バックアップできる
	os.Remove(filepath.Join(e.root, "2024/2024-05/IMG_0001.JPG"))
	fi.Owner = ""
	if m := e.begin(fi); m["status"] != "pending" {
		t.Fatalf("after delete = %v", m)
	}
}

func TestSameNameDifferentContentIsRenamed(t *testing.T) {
	e := newEnv(t, "")
	lm := time.Date(2020, 6, 1, 10, 0, 0, 0, time.Local).UnixMilli()
	a := []byte("first file")
	b := []byte("second file, longer")
	c := []byte("third file, even longer")
	e.upload(FileInfo{Name: "IMG_1.JPG", Size: int64(len(a)), LastModified: lm}, a, 100)
	r := e.upload(FileInfo{Name: "IMG_1.JPG", Size: int64(len(b)), LastModified: lm}, b, 100)
	if r["path"] != "2020/2020-06/IMG_1 (1).JPG" {
		t.Fatalf("path = %v", r["path"])
	}
	r = e.upload(FileInfo{Name: "IMG_1.JPG", Size: int64(len(c)), LastModified: lm}, c, 100)
	if r["path"] != "2020/2020-06/IMG_1 (2).JPG" {
		t.Fatalf("path = %v", r["path"])
	}
	got, _ := os.ReadFile(filepath.Join(e.root, "2020/2020-06/IMG_1.JPG"))
	if !bytes.Equal(got, a) {
		t.Fatal("original file was overwritten")
	}
}

func TestExistingIdenticalFileNotDuplicated(t *testing.T) {
	// index に無くても、同じ場所に同じ内容のファイルがあれば重複させない
	e := newEnv(t, "")
	data := readFixture(t, "testdata/exif.jpg")
	dir := filepath.Join(e.root, "2024", "2024-05")
	os.MkdirAll(dir, 0o755)
	os.WriteFile(filepath.Join(dir, "IMG_0001.JPG"), data, 0o644)

	r := e.upload(FileInfo{Name: "IMG_0001.JPG", Size: int64(len(data))}, data, 1<<20)
	if r["path"] != "2024/2024-05/IMG_0001.JPG" {
		t.Fatalf("path = %v", r["path"])
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 {
		t.Fatalf("expected 1 file, got %d", len(entries))
	}
}

func TestResumeAfterInterruption(t *testing.T) {
	e := newEnv(t, "")
	data := bytes.Repeat([]byte("0123456789"), 1000)
	fi := FileInfo{Name: "big.mov", Size: int64(len(data)), LastModified: time.Now().UnixMilli()}
	m := e.begin(fi)
	id := m["id"].(string)
	if code, _ := e.put(id, 0, data[:3000]); code != 200 {
		t.Fatal(code)
	}

	// ページを開き直した想定: 同じファイルで begin すると続きの位置が返る
	m = e.begin(fi)
	if m["id"] != id || m["offset"].(float64) != 3000 {
		t.Fatalf("resume = %v", m)
	}

	// 位置がずれた送信は 409 と正しい位置を返す
	code, r := e.put(id, 1000, data[1000:2000])
	if code != http.StatusConflict || r["offset"].(float64) != 3000 {
		t.Fatalf("conflict = %d %v", code, r)
	}

	// サーバー再起動後も続きから送れる
	e.store.Close()
	store2, err := NewStore(e.root, "date")
	if err != nil {
		t.Fatal(err)
	}
	defer store2.Close()
	srv2 := httptest.NewServer(NewServer(store2, "", fstest.MapFS{}))
	defer srv2.Close()
	e.srv = srv2
	code, r = e.put(id, 3000, data[3000:])
	if code != 200 || r["status"] != "done" {
		t.Fatalf("final = %d %v", code, r)
	}
	got, _ := os.ReadFile(filepath.Join(e.root, filepath.FromSlash(r["path"].(string))))
	if !bytes.Equal(got, data) {
		t.Fatal("content mismatch after resume")
	}
}

func TestRejectsOversizeAndBadRequests(t *testing.T) {
	e := newEnv(t, "")
	m := e.begin(FileInfo{Name: "a.jpg", Size: 5})
	id := m["id"].(string)
	if code, _ := e.put(id, 0, []byte("123456")); code != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversize = %d", code)
	}
	// 失敗した書き込みは残らない
	if m := e.begin(FileInfo{Name: "a.jpg", Size: 5}); m["offset"].(float64) != 0 {
		t.Fatalf("offset after oversize = %v", m)
	}
	if code, _ := e.put(id, 0, nil); code != 200 {
		t.Fatalf("empty chunk = %d", code)
	}
	if code, _ := e.do("PUT", "/api/uploads/"+id, strings.NewReader("x"), nil); code != http.StatusBadRequest {
		t.Fatalf("missing offset = %d", code)
	}
	if code, _ := e.put("..%2F..%2Fetc%2Fpasswd", 0, []byte("x")); code != http.StatusNotFound {
		t.Fatalf("bad id = %d", code)
	}
	if code, _ := e.put(strings.Repeat("a", 32), 0, []byte("x")); code != http.StatusNotFound {
		t.Fatalf("unknown id = %d", code)
	}
	for _, body := range []string{`{"name":"","size":1}`, `{"name":"..","size":1}`, `{"name":"a.jpg","size":-1}`, `not json`} {
		if code, _ := e.do("POST", "/api/uploads", strings.NewReader(body), nil); code != http.StatusBadRequest {
			t.Errorf("%s => %d", body, code)
		}
	}
}

func TestPathTraversalIsNeutralized(t *testing.T) {
	e := newEnv(t, "")
	data := []byte("x")
	lm := time.Date(2020, 1, 1, 0, 0, 0, 0, time.Local).UnixMilli()
	r := e.upload(FileInfo{Name: "../../../evil.txt", Size: 1, LastModified: lm}, data, 10)
	if r["path"] != "2020/2020-01/evil.txt" {
		t.Fatalf("path = %v", r["path"])
	}
	// フォルダ名として使えない保存先は拒否する
	body := `{"name":"x.jpg","size":1,"owner":"../.."}`
	if code, _ := e.do("POST", "/api/uploads", strings.NewReader(body), nil); code != http.StatusBadRequest {
		t.Fatalf("bad owner = %d", code)
	}
	r = e.upload(FileInfo{Name: `..\..\win.txt`, Size: 1, LastModified: lm, Owner: "a/b"}, data, 10)
	if r["path"] != "b/2020/2020-01/win.txt" {
		t.Fatalf("path = %v", r["path"])
	}
	if _, err := os.Stat(filepath.Join(filepath.Dir(e.root), "evil.txt")); err == nil {
		t.Fatal("file written outside of backup dir")
	}
}

func TestZeroByteFile(t *testing.T) {
	e := newEnv(t, "")
	r := e.upload(FileInfo{Name: "empty.jpg", Size: 0}, nil, 10)
	if r["status"] != "done" {
		t.Fatalf("zero byte = %v", r)
	}
}

func TestPasswordProtection(t *testing.T) {
	e := newEnv(t, "secret")
	if code, _ := e.do("GET", "/api/status", nil, nil); code != http.StatusUnauthorized {
		t.Fatalf("no auth = %d", code)
	}
	req, _ := http.NewRequest("GET", e.srv.URL+"/", nil)
	req.SetBasicAuth("any", "wrong")
	if res, _ := http.DefaultClient.Do(req); res.StatusCode != http.StatusUnauthorized {
		t.Fatalf("wrong password = %d", res.StatusCode)
	}
	req.SetBasicAuth("any", "secret")
	res, err := http.DefaultClient.Do(req)
	if err != nil || res.StatusCode != 200 {
		t.Fatalf("correct password = %v %v", res.StatusCode, err)
	}
}

func TestStatus(t *testing.T) {
	e := newEnv(t, "")
	code, m := e.do("GET", "/api/status", nil, nil)
	if code != 200 || m["layout"] != "date" || m["chunkSize"].(float64) <= 0 {
		t.Fatalf("status = %d %v", code, m)
	}
}

func TestCleanupStale(t *testing.T) {
	e := newEnv(t, "")
	m := e.begin(FileInfo{Name: "old.mov", Size: 100})
	id := m["id"].(string)
	e.put(id, 0, make([]byte, 10))
	meta, part := e.store.sessionPaths(id)
	old := time.Now().Add(-8 * 24 * time.Hour)
	os.Chtimes(part, old, old)
	e.store.CleanupStale(staleAfter)
	for _, p := range []string{meta, part} {
		if _, err := os.Stat(p); err == nil {
			t.Errorf("%s not removed", p)
		}
	}
}

func TestSanitizeName(t *testing.T) {
	tests := map[string]string{
		"IMG_0001.JPG":       "IMG_0001.JPG",
		"写真 2024.heic":       "写真 2024.heic",
		"a/b/c.jpg":          "c.jpg",
		`C:\Users\x\d.jpg`:   "d.jpg",
		"what?.jpg":          "what_.jpg",
		".hidden":            "hidden",
		" spaced .jpg. ":     "spaced .jpg",
		"tab\there.jpg":      "tabhere.jpg",
		".nasbackup":         "nasbackup",
		"name\x00inject.jpg": "nameinject.jpg",
	}
	for in, want := range tests {
		got, err := sanitizeName(in, 200)
		if err != nil || got != want {
			t.Errorf("sanitizeName(%q) = %q, %v; want %q", in, got, err, want)
		}
	}
	for _, in := range []string{"", ".", "..", "/", "a/..", "   "} {
		if got, err := sanitizeName(in, 200); err == nil {
			t.Errorf("sanitizeName(%q) = %q, want error", in, got)
		}
	}
	long := strings.Repeat("あ", 100) + ".jpg" // 300 バイト + 拡張子
	got, err := sanitizeName(long, 200)
	if err != nil || len(got) > 200 || !strings.HasSuffix(got, "あ.jpg") {
		t.Errorf("long name = %q (%d bytes), %v", got, len(got), err)
	}
}

func TestMissingBackupDirIsNotCreated(t *testing.T) {
	// NAS がマウントされていないときにローカルへ書き込まないよう、保存先フォルダは自動作成しない
	missing := filepath.Join(t.TempDir(), "not-mounted", "SmartphoneBackup")
	if _, err := NewStore(missing, "date"); !errors.Is(err, ErrNoBackupDir) {
		t.Fatalf("err = %v, want ErrNoBackupDir", err)
	}
	if _, err := os.Stat(missing); err == nil {
		t.Fatal("backup dir was created")
	}
}
