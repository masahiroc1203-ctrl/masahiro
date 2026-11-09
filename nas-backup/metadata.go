package main

// 写真・動画ファイルから「撮影日時」を読み取る。
// 外部ライブラリを使わず、以下の形式に対応する:
//   - JPEG (EXIF)
//   - HEIC / HEIF / AVIF (ISOBMFF の Exif アイテム)
//   - MP4 / MOV / 3GP (moov/mvhd の作成日時)
//   - TIFF ベースの RAW (DNG など)
// 読み取れない場合は ok=false を返し、呼び出し側でファイルの更新日時などにフォールバックする。

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"errors"
	"io"
	"strings"
	"time"
)

// CaptureTime はファイルの撮影日時を推定する。
func CaptureTime(r io.ReadSeeker) (time.Time, bool) {
	var head [12]byte
	if _, err := r.Seek(0, io.SeekStart); err != nil {
		return time.Time{}, false
	}
	n, _ := io.ReadFull(r, head[:])
	if n < 8 {
		return time.Time{}, false
	}

	var (
		t  time.Time
		ok bool
	)
	switch {
	case head[0] == 0xFF && head[1] == 0xD8:
		t, ok = jpegTime(r)
	case string(head[4:8]) == "ftyp":
		t, ok = isoBMFFTime(r)
	case string(head[0:4]) == "II*\x00" || string(head[0:4]) == "MM\x00*":
		// TIFF / DNG など。先頭から TIFF 構造なので直接読む。
		buf, err := readAt(r, 0, 4<<20)
		if err == nil || errors.Is(err, io.ErrUnexpectedEOF) {
			t, ok = tiffTime(buf)
		}
	}
	if !ok || !plausible(t) {
		return time.Time{}, false
	}
	return t, true
}

// plausible はデジカメ・スマホの初期値 (1904年や1970年) や未来の日時を弾く。
func plausible(t time.Time) bool {
	if t.IsZero() || t.Year() < 1990 {
		return false
	}
	return t.Before(time.Now().Add(48 * time.Hour))
}

func readAt(r io.ReadSeeker, off, n int64) ([]byte, error) {
	if _, err := r.Seek(off, io.SeekStart); err != nil {
		return nil, err
	}
	buf := make([]byte, n)
	m, err := io.ReadFull(r, buf)
	return buf[:m], err
}

// ---------------------------------------------------------------- JPEG

func jpegTime(r io.ReadSeeker) (time.Time, bool) {
	if _, err := r.Seek(2, io.SeekStart); err != nil {
		return time.Time{}, false
	}
	br := bufio.NewReader(r)
	for i := 0; i < 64; i++ { // APP1 は通常先頭付近にある
		b, err := br.ReadByte()
		if err != nil || b != 0xFF {
			return time.Time{}, false
		}
		marker, err := br.ReadByte()
		for err == nil && marker == 0xFF { // フィルバイト
			marker, err = br.ReadByte()
		}
		if err != nil {
			return time.Time{}, false
		}
		switch {
		case marker == 0xD9 || marker == 0xDA: // EOI / SOS: これ以降にメタデータはない
			return time.Time{}, false
		case marker == 0x01 || (marker >= 0xD0 && marker <= 0xD7): // 長さを持たないマーカー
			continue
		}
		var lb [2]byte
		if _, err := io.ReadFull(br, lb[:]); err != nil {
			return time.Time{}, false
		}
		segLen := int(binary.BigEndian.Uint16(lb[:])) - 2
		if segLen < 0 {
			return time.Time{}, false
		}
		if marker == 0xE1 && segLen > 6 {
			seg := make([]byte, segLen)
			if _, err := io.ReadFull(br, seg); err != nil {
				return time.Time{}, false
			}
			if bytes.HasPrefix(seg, []byte("Exif\x00\x00")) {
				if t, ok := tiffTime(seg[6:]); ok {
					return t, true
				}
			}
			continue
		}
		if _, err := br.Discard(segLen); err != nil {
			return time.Time{}, false
		}
	}
	return time.Time{}, false
}

// ---------------------------------------------------------------- TIFF / EXIF

const (
	tagDateTime          = 0x0132
	tagExifIFD           = 0x8769
	tagDateTimeOriginal  = 0x9003
	tagDateTimeDigitized = 0x9004
	tagOffsetTime        = 0x9010
	tagOffsetTimeOrig    = 0x9011
	tagOffsetTimeDigit   = 0x9012
)

type ifdEntry struct {
	tag   uint16
	typ   uint16
	count uint32
	value []byte // 4 バイトの値またはオフセット
}

// tiffTime は TIFF ヘッダから始まるバイト列 (EXIF 本体) から撮影日時を探す。
func tiffTime(b []byte) (time.Time, bool) {
	if len(b) < 8 {
		return time.Time{}, false
	}
	var bo binary.ByteOrder
	switch string(b[:2]) {
	case "II":
		bo = binary.LittleEndian
	case "MM":
		bo = binary.BigEndian
	default:
		return time.Time{}, false
	}
	if bo.Uint16(b[2:4]) != 42 {
		return time.Time{}, false
	}
	ifd0 := readIFD(b, bo, bo.Uint32(b[4:8]))

	var exif map[uint16]ifdEntry
	if e, ok := ifd0[tagExifIFD]; ok {
		exif = readIFD(b, bo, entryUint(bo, e))
	}

	candidates := []struct {
		dict      map[uint16]ifdEntry
		tag, zone uint16
	}{
		{exif, tagDateTimeOriginal, tagOffsetTimeOrig},
		{exif, tagDateTimeDigitized, tagOffsetTimeDigit},
		{ifd0, tagDateTime, tagOffsetTime},
	}
	for _, c := range candidates {
		if c.dict == nil {
			continue
		}
		e, ok := c.dict[c.tag]
		if !ok {
			continue
		}
		s, ok := entryASCII(b, bo, e)
		if !ok {
			continue
		}
		loc := time.Local
		if ze, ok := exif[c.zone]; ok {
			if zs, ok := entryASCII(b, bo, ze); ok {
				if l, ok := parseZone(zs); ok {
					loc = l
				}
			}
		}
		t, err := time.ParseInLocation("2006:01:02 15:04:05", s, loc)
		if err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

func readIFD(b []byte, bo binary.ByteOrder, off uint32) map[uint16]ifdEntry {
	if int64(off)+2 > int64(len(b)) {
		return nil
	}
	n := int(bo.Uint16(b[off:]))
	p := int(off) + 2
	m := make(map[uint16]ifdEntry, n)
	for i := 0; i < n && p+12 <= len(b); i++ {
		m[bo.Uint16(b[p:])] = ifdEntry{
			tag:   bo.Uint16(b[p:]),
			typ:   bo.Uint16(b[p+2:]),
			count: bo.Uint32(b[p+4:]),
			value: b[p+8 : p+12],
		}
		p += 12
	}
	return m
}

func entryUint(bo binary.ByteOrder, e ifdEntry) uint32 {
	if e.typ == 3 { // SHORT
		return uint32(bo.Uint16(e.value))
	}
	return bo.Uint32(e.value)
}

func entryASCII(b []byte, bo binary.ByteOrder, e ifdEntry) (string, bool) {
	if e.typ != 2 || e.count == 0 || e.count > 256 {
		return "", false
	}
	var raw []byte
	if e.count <= 4 {
		raw = e.value[:e.count]
	} else {
		off := int64(bo.Uint32(e.value))
		if off+int64(e.count) > int64(len(b)) {
			return "", false
		}
		raw = b[off : off+int64(e.count)]
	}
	if i := bytes.IndexByte(raw, 0); i >= 0 {
		raw = raw[:i]
	}
	return strings.TrimSpace(string(raw)), true
}

// parseZone は "+09:00" 形式のタイムゾーンを読む。
func parseZone(s string) (*time.Location, bool) {
	t, err := time.Parse("-07:00", strings.TrimSpace(s))
	if err != nil {
		return nil, false
	}
	_, off := t.Zone()
	return time.FixedZone(s, off), true
}

// ---------------------------------------------------------------- ISOBMFF (HEIC / MP4 / MOV)

type box struct {
	typ        string
	start, end int64 // ボックス全体の範囲
	data       int64 // ヘッダ直後 (ペイロード開始位置)
}

func readBox(r io.ReadSeeker, pos, limit int64) (box, error) {
	if pos+8 > limit {
		return box{}, io.EOF
	}
	hdr, err := readAt(r, pos, 16)
	if len(hdr) < 8 {
		if err == nil {
			err = io.ErrUnexpectedEOF
		}
		return box{}, err
	}
	size := int64(binary.BigEndian.Uint32(hdr[0:4]))
	b := box{typ: string(hdr[4:8]), start: pos, data: pos + 8}
	switch size {
	case 0: // ファイル末尾まで
		size = limit - pos
	case 1: // 64bit サイズ
		if len(hdr) < 16 {
			return box{}, io.ErrUnexpectedEOF
		}
		size = int64(binary.BigEndian.Uint64(hdr[8:16]))
		b.data = pos + 16
	}
	b.end = pos + size
	if size < b.data-pos || b.end > limit || b.end < pos {
		return box{}, errors.New("invalid box size")
	}
	return b, nil
}

// children は [from, to) に並ぶ子ボックスを列挙する。
func children(r io.ReadSeeker, from, to int64) []box {
	var out []box
	for pos := from; pos < to && len(out) < 4096; {
		b, err := readBox(r, pos, to)
		if err != nil {
			break
		}
		out = append(out, b)
		pos = b.end
	}
	return out
}

func isoBMFFTime(r io.ReadSeeker) (time.Time, bool) {
	size, err := r.Seek(0, io.SeekEnd)
	if err != nil {
		return time.Time{}, false
	}
	top := children(r, 0, size)
	// HEIC/HEIF: meta ボックス内の Exif アイテム
	for _, b := range top {
		if b.typ == "meta" {
			if t, ok := heifExifTime(r, b); ok {
				return t, true
			}
		}
	}
	// MP4/MOV: moov/mvhd の作成日時 (UTC)
	for _, b := range top {
		if b.typ != "moov" {
			continue
		}
		for _, c := range children(r, b.data, b.end) {
			if c.typ == "mvhd" {
				return mvhdTime(r, c)
			}
		}
	}
	return time.Time{}, false
}

var mp4Epoch = time.Date(1904, 1, 1, 0, 0, 0, 0, time.UTC)

func mvhdTime(r io.ReadSeeker, b box) (time.Time, bool) {
	buf, _ := readAt(r, b.data, 12)
	if len(buf) < 8 {
		return time.Time{}, false
	}
	var secs uint64
	if buf[0] == 1 {
		if len(buf) < 12 {
			return time.Time{}, false
		}
		secs = binary.BigEndian.Uint64(buf[4:12])
	} else {
		secs = uint64(binary.BigEndian.Uint32(buf[4:8]))
	}
	if secs == 0 || secs > 1<<40 {
		return time.Time{}, false
	}
	return mp4Epoch.Add(time.Duration(secs) * time.Second).In(time.Local), true
}

type extent struct{ off, length int64 }

func heifExifTime(r io.ReadSeeker, meta box) (time.Time, bool) {
	// meta は FullBox (version + flags の 4 バイト) の後に子ボックスが続く
	kids := children(r, meta.data+4, meta.end)
	var (
		exifID  uint32
		found   bool
		iloc    box
		hasIloc bool
		idat    box
		hasIdat bool
	)
	for _, k := range kids {
		switch k.typ {
		case "iinf":
			exifID, found = findExifItem(r, k)
		case "iloc":
			iloc, hasIloc = k, true
		case "idat":
			idat, hasIdat = k, true
		}
	}
	if !found || !hasIloc {
		return time.Time{}, false
	}
	method, exts, ok := itemLocation(r, iloc, exifID)
	if !ok {
		return time.Time{}, false
	}
	var data []byte
	for _, e := range exts {
		off := e.off
		switch method {
		case 0: // ファイル先頭からのオフセット
		case 1: // idat ボックス内のオフセット
			if !hasIdat {
				return time.Time{}, false
			}
			off += idat.data
		default:
			return time.Time{}, false
		}
		if e.length <= 0 || e.length > 4<<20 || len(data) > 4<<20 {
			return time.Time{}, false
		}
		chunk, err := readAt(r, off, e.length)
		if err != nil {
			return time.Time{}, false
		}
		data = append(data, chunk...)
	}
	// Exif アイテム: 先頭 4 バイトが TIFF ヘッダまでのオフセット
	if len(data) < 12 {
		return time.Time{}, false
	}
	skip := int64(binary.BigEndian.Uint32(data[:4]))
	if 4+skip < int64(len(data)) {
		if t, ok := tiffTime(data[4+skip:]); ok {
			return t, true
		}
	}
	// オフセットが不正なファイル向けのフォールバック
	for _, sig := range [][]byte{[]byte("MM\x00*"), []byte("II*\x00")} {
		if i := bytes.Index(data[:min(len(data), 64)], sig); i >= 0 {
			if t, ok := tiffTime(data[i:]); ok {
				return t, true
			}
		}
	}
	return time.Time{}, false
}

func findExifItem(r io.ReadSeeker, iinf box) (uint32, bool) {
	hdr, _ := readAt(r, iinf.data, 8)
	if len(hdr) < 6 {
		return 0, false
	}
	start := iinf.data + 6 // version/flags(4) + entry_count(2)
	if hdr[0] != 0 {
		start = iinf.data + 8 // entry_count が 4 バイト
	}
	for _, infe := range children(r, start, iinf.end) {
		if infe.typ != "infe" {
			continue
		}
		b, _ := readAt(r, infe.data, 14)
		if len(b) < 12 {
			continue
		}
		var id uint32
		var itemType string
		switch b[0] { // version
		case 2:
			id = uint32(binary.BigEndian.Uint16(b[4:6]))
			itemType = string(b[8:12])
		case 3:
			if len(b) < 14 {
				continue
			}
			id = binary.BigEndian.Uint32(b[4:8])
			itemType = string(b[10:14])
		default:
			continue
		}
		if itemType == "Exif" {
			return id, true
		}
	}
	return 0, false
}

func itemLocation(r io.ReadSeeker, iloc box, want uint32) (int, []extent, bool) {
	n := iloc.end - iloc.data
	if n < 8 || n > 1<<20 {
		return 0, nil, false
	}
	b, err := readAt(r, iloc.data, n)
	if err != nil {
		return 0, nil, false
	}
	p := &byteReader{b: b}
	version := p.uint(1)
	p.skip(3) // flags
	sizes := p.uint(1)
	offSize, lenSize := int(sizes>>4), int(sizes&0xF)
	sizes = p.uint(1)
	baseSize, idxSize := int(sizes>>4), int(sizes&0xF)
	if version != 1 && version != 2 {
		idxSize = 0
	}
	var count uint64
	if version < 2 {
		count = p.uint(2)
	} else {
		count = p.uint(4)
	}
	for i := uint64(0); i < count && !p.bad; i++ {
		var id uint64
		if version < 2 {
			id = p.uint(2)
		} else {
			id = p.uint(4)
		}
		method := 0
		if version == 1 || version == 2 {
			method = int(p.uint(2) & 0xF)
		}
		p.skip(2) // data_reference_index
		base := int64(p.uint(baseSize))
		extCount := int(p.uint(2))
		var exts []extent
		for j := 0; j < extCount && !p.bad; j++ {
			p.skip(idxSize)
			off := int64(p.uint(offSize))
			length := int64(p.uint(lenSize))
			exts = append(exts, extent{off: base + off, length: length})
		}
		if !p.bad && uint32(id) == want {
			return method, exts, len(exts) > 0
		}
	}
	return 0, nil, false
}

// byteReader はビッグエンディアンの可変長整数を順に読む小さなヘルパー。
type byteReader struct {
	b   []byte
	p   int
	bad bool
}

func (r *byteReader) uint(size int) uint64 {
	if size == 0 {
		return 0
	}
	if size > 8 || r.p+size > len(r.b) {
		r.bad = true
		return 0
	}
	var v uint64
	for _, c := range r.b[r.p : r.p+size] {
		v = v<<8 | uint64(c)
	}
	r.p += size
	return v
}

func (r *byteReader) skip(n int) {
	if r.p+n > len(r.b) {
		r.bad = true
		return
	}
	r.p += n
}
