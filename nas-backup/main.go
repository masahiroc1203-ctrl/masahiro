// nas-backup: スマホの写真・動画を家の NAS へバックアップする小さな Web アプリ。
//
// NAS (または家の PC) でこのサーバーを動かし、同じ Wi-Fi に接続したスマホの
// ブラウザから http://<NASのIP>:8080 を開いてファイルを選ぶだけで保存できる。
package main

import (
	"context"
	"embed"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	_ "time/tzdata" // Docker の最小イメージでも TZ=Asia/Tokyo を使えるようにする
)

const version = "1.0.0"

//go:embed web
var webFiles embed.FS

func main() {
	addr := flag.String("addr", env("LISTEN_ADDR", ":8080"), "待ち受けアドレス (環境変数 LISTEN_ADDR)")
	dir := flag.String("dir", env("BACKUP_DIR", "./backup"), "保存先ディレクトリ (環境変数 BACKUP_DIR)")
	layout := flag.String("layout", env("BACKUP_LAYOUT", "date"), `フォルダ分け: "date"=撮影年月ごと, "flat"=分けない (環境変数 BACKUP_LAYOUT)`)
	password := flag.String("password", os.Getenv("BACKUP_PASSWORD"), "アクセス用パスワード。空なら不要 (環境変数 BACKUP_PASSWORD 推奨)")
	showVersion := flag.Bool("version", false, "バージョンを表示して終了")
	flag.Parse()

	if *showVersion {
		fmt.Println(version)
		return
	}

	store, err := NewStore(*dir, *layout)
	if err != nil {
		log.Fatalf("保存先を開けません (%s): %v", *dir, err)
	}
	defer store.Close()

	static, err := fs.Sub(webFiles, "web")
	if err != nil {
		log.Fatal(err)
	}

	store.CleanupStale(staleAfter)
	go func() {
		for range time.Tick(6 * time.Hour) {
			store.CleanupStale(staleAfter)
		}
	}()

	srv := &http.Server{
		Addr:              *addr,
		Handler:           NewServer(store, *password, static),
		ReadHeaderTimeout: 30 * time.Second,
		IdleTimeout:       2 * time.Minute,
	}

	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatalf("ポート %s を開けません: %v", *addr, err)
	}
	log.Printf("nas-backup %s", version)
	log.Printf("保存先: %s (フォルダ分け: %s)", store.Root(), *layout)
	if *password != "" {
		log.Printf("パスワード保護: 有効")
	}
	for _, u := range lanURLs(ln.Addr()) {
		log.Printf("スマホのブラウザで開く: %s", u)
	}

	go func() {
		ch := make(chan os.Signal, 1)
		signal.Notify(ch, os.Interrupt, syscall.SIGTERM)
		<-ch
		log.Printf("停止しています…")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()

	if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// lanURLs は家庭内ネットワークからアクセスできそうな URL を列挙する。
func lanURLs(a net.Addr) []string {
	tcp, ok := a.(*net.TCPAddr)
	if !ok {
		return nil
	}
	if tcp.IP != nil && !tcp.IP.IsUnspecified() {
		return []string{fmt.Sprintf("http://%s", tcp.String())}
	}
	hint := fmt.Sprintf("http://<NASのIPアドレス>:%d", tcp.Port)
	if _, err := os.Stat("/.dockerenv"); err == nil {
		// コンテナ内からは NAS 本体の IP アドレスが分からない
		return []string{hint}
	}
	var urls []string
	addrs, _ := net.InterfaceAddrs()
	for _, ad := range addrs {
		ipn, ok := ad.(*net.IPNet)
		if !ok || ipn.IP.IsLoopback() || ipn.IP.To4() == nil {
			continue
		}
		urls = append(urls, fmt.Sprintf("http://%s:%d", ipn.IP, tcp.Port))
	}
	if len(urls) == 0 {
		urls = append(urls, hint)
	}
	return urls
}
