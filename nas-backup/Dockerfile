# マルチアーキテクチャ対応 (Intel/AMD の NAS も ARM の NAS / Raspberry Pi も同じ手順でビルドできる)
FROM --platform=$BUILDPLATFORM golang:1.24-alpine AS build
ARG TARGETOS TARGETARCH TARGETVARIANT
WORKDIR /src
COPY go.mod ./
COPY *.go ./
COPY web ./web
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH GOARM=${TARGETVARIANT#v} \
    go build -trimpath -ldflags="-s -w" -o /out/nas-backup .

FROM scratch
COPY --from=build /out/nas-backup /nas-backup
ENV BACKUP_DIR=/backup \
    LISTEN_ADDR=:8080 \
    TZ=Asia/Tokyo
EXPOSE 8080
VOLUME ["/backup"]
ENTRYPOINT ["/nas-backup"]
