package main

import (
	"bytes"
	"encoding/binary"
	"os"
	"testing"
	"time"
)

func mustOpen(t *testing.T, name string) *os.File {
	t.Helper()
	f, err := os.Open(name)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { f.Close() })
	return f
}

func TestCaptureTimeFixtures(t *testing.T) {
	jst := time.FixedZone("+09:00", 9*3600)
	tests := []struct {
		file string
		want time.Time
		ok   bool
	}{
		// DateTime (編集日時) より DateTimeOriginal (撮影日時) が優先され、OffsetTimeOriginal も反映される
		{"testdata/exif.jpg", time.Date(2024, 5, 3, 14, 15, 16, 0, jst), true},
		{"testdata/noexif.jpg", time.Time{}, false},
		// moov がファイル末尾にある MP4
		{"testdata/video.mp4", time.Date(2023, 8, 10, 1, 2, 3, 0, time.UTC), true},
		// moov が先頭にある MOV
		{"testdata/video.mov", time.Date(2022, 12, 31, 23, 30, 0, 0, time.UTC), true},
	}
	for _, tc := range tests {
		t.Run(tc.file, func(t *testing.T) {
			got, ok := CaptureTime(mustOpen(t, tc.file))
			if ok != tc.ok {
				t.Fatalf("ok = %v, want %v", ok, tc.ok)
			}
			if ok && !got.Equal(tc.want) {
				t.Fatalf("time = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestEXIFLocalWallClockKept(t *testing.T) {
	// OffsetTime が無い場合は撮影時の見た目の日時 (壁時計) をそのまま使う
	tiff := buildTIFF(binary.BigEndian, "2021:12:31 23:59:59", "")
	got, ok := CaptureTime(bytes.NewReader(wrapJPEG(tiff)))
	if !ok {
		t.Fatal("not found")
	}
	if got.Format("2006-01-02 15:04:05") != "2021-12-31 23:59:59" {
		t.Fatalf("got %v", got)
	}
}

func TestEXIFByteOrders(t *testing.T) {
	for _, bo := range []binary.ByteOrder{binary.BigEndian, binary.LittleEndian} {
		tiff := buildTIFF(bo, "2019:07:08 09:10:11", "-05:00")
		got, ok := CaptureTime(bytes.NewReader(wrapJPEG(tiff)))
		want := time.Date(2019, 7, 8, 9, 10, 11, 0, time.FixedZone("", -5*3600))
		if !ok || !got.Equal(want) {
			t.Fatalf("%v: got %v %v", bo, got, ok)
		}
		// TIFF / DNG としてそのまま読めること
		got, ok = CaptureTime(bytes.NewReader(tiff))
		if !ok || !got.Equal(want) {
			t.Fatalf("%v tiff: got %v %v", bo, got, ok)
		}
	}
}

func TestEXIFInvalidValues(t *testing.T) {
	for _, s := range []string{"0000:00:00 00:00:00", "    :  :     :  :  ", "1970:01:01 00:00:00", "2999:01:01 00:00:00"} {
		if got, ok := CaptureTime(bytes.NewReader(wrapJPEG(buildTIFF(binary.BigEndian, s, "")))); ok {
			t.Errorf("%q: unexpectedly parsed as %v", s, got)
		}
	}
}

func TestHEIC(t *testing.T) {
	want := time.Date(2025, 2, 14, 8, 30, 0, 0, time.FixedZone("", 9*3600))
	for _, v := range []byte{0, 1} {
		data := buildHEIC(t, buildTIFF(binary.BigEndian, "2025:02:14 08:30:00", "+09:00"), v)
		got, ok := CaptureTime(bytes.NewReader(data))
		if !ok || !got.Equal(want) {
			t.Fatalf("iloc v%d: got %v %v", v, got, ok)
		}
	}
}

func TestMP4Versions(t *testing.T) {
	want := time.Date(2024, 1, 2, 3, 4, 5, 0, time.UTC)
	secs := uint64(want.Sub(mp4Epoch) / time.Second)
	for _, v := range []byte{0, 1} {
		var mvhd []byte
		if v == 0 {
			mvhd = append([]byte{0, 0, 0, 0}, be32(uint32(secs))...)
			mvhd = append(mvhd, be32(uint32(secs))...)
		} else {
			mvhd = append([]byte{1, 0, 0, 0}, be64(secs)...)
			mvhd = append(mvhd, be64(secs)...)
		}
		mvhd = append(mvhd, make([]byte, 80)...)
		file := cat(
			mkbox("ftyp", []byte("isom\x00\x00\x02\x00isomiso2")),
			mkbox("mdat", make([]byte, 100)),
			mkbox("moov", mkbox("mvhd", mvhd)),
		)
		got, ok := CaptureTime(bytes.NewReader(file))
		if !ok || !got.Equal(want) {
			t.Fatalf("mvhd v%d: got %v %v", v, got, ok)
		}
	}
	// 作成日時 0 (未設定) は無視
	file := cat(mkbox("ftyp", []byte("isom\x00\x00\x02\x00")), mkbox("moov", mkbox("mvhd", make([]byte, 100))))
	if _, ok := CaptureTime(bytes.NewReader(file)); ok {
		t.Fatal("zero creation time should be ignored")
	}
}

func TestCaptureTimeGarbage(t *testing.T) {
	// 壊れたデータでパニックしないこと
	inputs := [][]byte{
		nil,
		[]byte("hello world, not an image"),
		{0xFF, 0xD8, 0xFF, 0xE1, 0x00, 0x02},
		{0xFF, 0xD8, 0xFF, 0xE1, 0xFF, 0xFF, 'E', 'x', 'i', 'f', 0, 0},
		append([]byte{0, 0, 0, 8}, []byte("ftyp")...),
		append([]byte{0xFF, 0xFF, 0xFF, 0xFF}, []byte("ftypheic")...),
		[]byte("II*\x00\xff\xff\xff\xff"),
		[]byte("MM\x00*\x00\x00\x00\x08\xff\xff"),
	}
	full := buildHEIC(t, buildTIFF(binary.BigEndian, "2025:02:14 08:30:00", ""), 1)
	for i := 0; i < len(full); i += 7 {
		inputs = append(inputs, full[:i])
	}
	for _, in := range inputs {
		CaptureTime(bytes.NewReader(in))
	}
}

// ---------------------------------------------------------------- テスト用データ生成

func be16(v uint16) []byte { b := make([]byte, 2); binary.BigEndian.PutUint16(b, v); return b }
func be32(v uint32) []byte { b := make([]byte, 4); binary.BigEndian.PutUint32(b, v); return b }
func be64(v uint64) []byte { b := make([]byte, 8); binary.BigEndian.PutUint64(b, v); return b }

func cat(parts ...[]byte) []byte { return bytes.Join(parts, nil) }

func mkbox(typ string, payload []byte) []byte {
	return cat(be32(uint32(8+len(payload))), []byte(typ), payload)
}

// buildTIFF は IFD0 -> ExifIFD -> DateTimeOriginal (+ OffsetTimeOriginal) を持つ最小の TIFF を作る。
func buildTIFF(bo binary.ByteOrder, date, offset string) []byte {
	var b bytes.Buffer
	if bo == binary.LittleEndian {
		b.WriteString("II")
	} else {
		b.WriteString("MM")
	}
	w16 := func(v uint16) { binary.Write(&b, bo, v) }
	w32 := func(v uint32) { binary.Write(&b, bo, v) }
	w16(42)
	w32(8)
	// IFD0 (offset 8): 1 entry
	w16(1)
	exifOff := uint32(8 + 2 + 12 + 4)
	w16(tagExifIFD)
	w16(4)
	w32(1)
	w32(exifOff)
	w32(0)
	// Exif IFD
	n := uint16(1)
	if offset != "" {
		n = 2
	}
	w16(n)
	dataOff := exifOff + 2 + uint32(n)*12 + 4
	dateBytes := append([]byte(date), 0)
	w16(tagDateTimeOriginal)
	w16(2)
	w32(uint32(len(dateBytes)))
	w32(dataOff)
	var offBytes []byte
	if offset != "" {
		offBytes = append([]byte(offset), 0)
		w16(tagOffsetTimeOrig)
		w16(2)
		w32(uint32(len(offBytes)))
		w32(dataOff + uint32(len(dateBytes)))
	}
	w32(0)
	b.Write(dateBytes)
	b.Write(offBytes)
	return b.Bytes()
}

func wrapJPEG(tiff []byte) []byte {
	app1 := cat([]byte("Exif\x00\x00"), tiff)
	return cat(
		[]byte{0xFF, 0xD8},
		[]byte{0xFF, 0xE0}, be16(16), []byte("JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"),
		[]byte{0xFF, 0xE1}, be16(uint16(len(app1)+2)), app1,
		[]byte{0xFF, 0xDA, 0x00, 0x02},
		[]byte{0xFF, 0xD9},
	)
}

// buildHEIC は meta(iinf, iloc) と mdat に Exif アイテムを持つ最小の HEIF を作る。
func buildHEIC(t *testing.T, tiff []byte, ilocVersion byte) []byte {
	t.Helper()
	exifItem := cat(be32(6), []byte("Exif\x00\x00"), tiff)
	ftyp := mkbox("ftyp", []byte("heic\x00\x00\x00\x00mif1heic"))
	hdlr := mkbox("hdlr", cat(make([]byte, 8), []byte("pict"), make([]byte, 13)))
	infe := func(id uint16, typ string) []byte {
		return mkbox("infe", cat([]byte{2, 0, 0, 0}, be16(id), be16(0), []byte(typ), []byte{0}))
	}
	iinf := mkbox("iinf", cat([]byte{0, 0, 0, 0}, be16(2), infe(1, "hvc1"), infe(2, "Exif")))

	build := func(mdatOffset uint32) []byte {
		var p []byte
		p = append(p, ilocVersion, 0, 0, 0)
		p = append(p, 0x44, 0x00) // offset_size=4, length_size=4, base_offset_size=0, index_size=0
		p = append(p, be16(2)...)
		// item 1: 画像データ (ダミー)
		p = append(p, be16(1)...)
		if ilocVersion == 1 {
			p = append(p, be16(0)...) // construction_method = 0
		}
		p = append(p, be16(0)...) // data_reference_index
		p = append(p, be16(1)...) // extent_count
		p = append(p, be32(mdatOffset)...)
		p = append(p, be32(10)...)
		// item 2: Exif
		p = append(p, be16(2)...)
		if ilocVersion == 1 {
			p = append(p, be16(0)...)
		}
		p = append(p, be16(0)...)
		p = append(p, be16(1)...)
		p = append(p, be32(mdatOffset+10)...)
		p = append(p, be32(uint32(len(exifItem)))...)
		meta := mkbox("meta", cat([]byte{0, 0, 0, 0}, hdlr, iinf, mkbox("iloc", p)))
		return cat(ftyp, meta)
	}
	head := build(0)
	mdatPayloadStart := uint32(len(head) + 8)
	head = build(mdatPayloadStart)
	return cat(head, mkbox("mdat", cat(make([]byte, 10), exifItem)))
}
