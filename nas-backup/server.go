package main

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"io"
	"io/fs"
	"log"
	"net/http"
	"strconv"
)

const (
	defaultChunkSize = 8 << 20  // クライアントが 1 回に送るサイズ
	maxChunkSize     = 64 << 20 // サーバーが 1 リクエストで受け付ける上限
	maxCheckFiles    = 5000
)

type Server struct {
	store    *Store
	password string
	static   fs.FS
	mux      *http.ServeMux
}

func NewServer(store *Store, password string, static fs.FS) *Server {
	s := &Server{store: store, password: password, static: static, mux: http.NewServeMux()}
	s.mux.HandleFunc("GET /api/status", s.handleStatus)
	s.mux.HandleFunc("POST /api/check", s.handleCheck)
	s.mux.HandleFunc("POST /api/uploads", s.handleBegin)
	s.mux.HandleFunc("PUT /api/uploads/{id}", s.handleWrite)
	s.mux.Handle("GET /", staticHandler(static))
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if s.password != "" {
		_, pw, ok := r.BasicAuth()
		if !ok || subtle.ConstantTimeCompare([]byte(pw), []byte(s.password)) != 1 {
			w.Header().Set("WWW-Authenticate", `Basic realm="NAS Backup", charset="UTF-8"`)
			http.Error(w, "パスワードが必要です", http.StatusUnauthorized)
			return
		}
	}
	s.mux.ServeHTTP(w, r)
}

func staticHandler(static fs.FS) http.Handler {
	files := http.FileServer(http.FS(static))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 更新がすぐ反映されるようにキャッシュは毎回確認させる
		w.Header().Set("Cache-Control", "no-cache")
		files.ServeHTTP(w, r)
	})
}

func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	free, total, ok := diskSpace(s.store.Root())
	resp := map[string]any{
		"layout":    s.store.layout,
		"chunkSize": defaultChunkSize,
		"version":   version,
	}
	if ok {
		resp["freeBytes"] = free
		resp["totalBytes"] = total
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleCheck(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Owner string     `json:"owner"`
		Files []FileInfo `json:"files"`
	}
	if !readJSON(w, r, &req, 4<<20) {
		return
	}
	if len(req.Files) > maxCheckFiles {
		writeError(w, http.StatusRequestEntityTooLarge, "一度に確認できるのは5000件までです")
		return
	}
	type result struct {
		Exists bool   `json:"exists"`
		Path   string `json:"path,omitempty"`
	}
	out := make([]result, len(req.Files))
	for i, f := range req.Files {
		f.Owner = req.Owner
		p, ok := s.store.Exists(f)
		out[i] = result{Exists: ok, Path: p}
	}
	writeJSON(w, http.StatusOK, map[string]any{"files": out})
}

func (s *Server) handleBegin(w http.ResponseWriter, r *http.Request) {
	var fi FileInfo
	if !readJSON(w, r, &fi, 64<<10) {
		return
	}
	if free, _, ok := diskSpace(s.store.Root()); ok && fi.Size > 0 && uint64(fi.Size) > free {
		writeError(w, http.StatusInsufficientStorage, "NASの空き容量が足りません")
		return
	}
	res, err := s.store.Begin(fi)
	if err != nil {
		s.storeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, res)
}

func (s *Server) handleWrite(w http.ResponseWriter, r *http.Request) {
	offset, err := strconv.ParseInt(r.Header.Get("Upload-Offset"), 10, 64)
	if err != nil || offset < 0 {
		writeError(w, http.StatusBadRequest, "Upload-Offset ヘッダが不正です")
		return
	}
	body := http.MaxBytesReader(w, r.Body, maxChunkSize)
	res, err := s.store.Write(r.PathValue("id"), offset, body)
	if err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			writeError(w, http.StatusRequestEntityTooLarge, "1回の送信サイズが大きすぎます")
			return
		}
		if errors.Is(err, ErrOffset) {
			writeJSON(w, http.StatusConflict, res)
			return
		}
		s.storeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, res)
}

func (s *Server) storeError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrNotFound):
		writeError(w, http.StatusNotFound, "アップロード情報が見つかりません。最初からやり直してください")
	case errors.Is(err, ErrTooLarge):
		writeError(w, http.StatusRequestEntityTooLarge, "ファイルサイズが申告と異なります")
	case errors.Is(err, ErrInvalidName), errors.Is(err, ErrInvalidOwner), errors.Is(err, ErrInvalidSize):
		writeError(w, http.StatusBadRequest, err.Error())
	case errors.Is(err, io.ErrUnexpectedEOF):
		writeError(w, http.StatusBadRequest, "通信が途中で切れました")
	default:
		log.Printf("error: %v", err)
		writeError(w, http.StatusInternalServerError, "保存に失敗しました: "+err.Error())
	}
}

func readJSON(w http.ResponseWriter, r *http.Request, v any, limit int64) bool {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, limit))
	if err := dec.Decode(v); err != nil {
		writeError(w, http.StatusBadRequest, "リクエストが不正です")
		return false
	}
	return true
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]string{"error": msg})
}
