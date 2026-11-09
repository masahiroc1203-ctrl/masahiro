APP := nas-backup
LDFLAGS := -s -w

.PHONY: run build test dist docker clean

## 開発用: ./backup に保存するサーバーを起動
run:
	go run . -dir ./backup

build:
	CGO_ENABLED=0 go build -trimpath -ldflags="$(LDFLAGS)" -o $(APP) .

test:
	go vet ./...
	go test -race ./...

## 各環境向けの実行ファイルを dist/ に作る
dist:
	mkdir -p dist
	CGO_ENABLED=0 GOOS=linux   GOARCH=amd64       go build -trimpath -ldflags="$(LDFLAGS)" -o dist/$(APP)-linux-amd64 .
	CGO_ENABLED=0 GOOS=linux   GOARCH=arm64       go build -trimpath -ldflags="$(LDFLAGS)" -o dist/$(APP)-linux-arm64 .
	CGO_ENABLED=0 GOOS=linux   GOARCH=arm GOARM=7 go build -trimpath -ldflags="$(LDFLAGS)" -o dist/$(APP)-linux-armv7 .
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64       go build -trimpath -ldflags="$(LDFLAGS)" -o dist/$(APP)-windows-amd64.exe .
	CGO_ENABLED=0 GOOS=darwin  GOARCH=arm64       go build -trimpath -ldflags="$(LDFLAGS)" -o dist/$(APP)-macos-arm64 .

docker:
	docker build -t $(APP):latest .

clean:
	rm -rf dist $(APP) $(APP).exe
