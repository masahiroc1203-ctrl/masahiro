# 変数（make コマンド実行時に上書き可能）
INPUT     ?= input.mp4
OUTPUT    ?= output.mp4
REF       ?= 0
START     ?= 0.0
END       ?= 5.0
THRESHOLD ?= 0.92
PORT      ?= 8080

PYTHON    := PYTHONPATH=src python -m video_editor.cli

.PHONY: run dry-run preview inspect install test clean serve help

## 動画を処理して結合ファイルを出力する
run:
	$(PYTHON) run $(INPUT) $(OUTPUT) \
		--ref-frame $(REF) \
		--start $(START) \
		--end $(END) \
		--threshold $(THRESHOLD)

## 検出結果を確認する（ファイル出力なし）
dry-run:
	$(PYTHON) run $(INPUT) $(OUTPUT) \
		--ref-frame $(REF) \
		--start $(START) \
		--end $(END) \
		--threshold $(THRESHOLD) \
		--dry-run

## 類似度グラフを生成してサイクル検出を確認する
preview:
	$(PYTHON) preview $(INPUT) \
		--ref-frame $(REF) \
		--threshold $(THRESHOLD)

## 動画の情報を表示する
inspect:
	$(PYTHON) inspect $(INPUT)

## 依存ライブラリをインストールする
install:
	pip install -r requirements.txt
	pip install -e .

## テストを実行する
test:
	PYTHONPATH=src pytest tests/ -v --tb=short

## Web UIを起動する
serve:
	uvicorn web.app:app --host 0.0.0.0 --port $(PORT) --reload

## exe ファイルをビルドする（Windows: build_exe.bat を使用）
build-exe:
	pip install pyinstaller -q
	pyinstaller video_editor.spec --noconfirm

## 一時ファイルと出力ファイルを削除する
clean:
	rm -rf tmp/ uploads/ outputs/ $(OUTPUT) detection_preview.png

help:
	@grep -E '^##' Makefile | sed 's/## //'
	@echo ""
	@echo "使用例:"
	@echo "  make inspect INPUT=factory.mp4"
	@echo "  make dry-run INPUT=factory.mp4 REF=156 START=2 END=8"
	@echo "  make run     INPUT=factory.mp4 OUTPUT=result.mp4 REF=156 START=2 END=8"
	@echo "  make serve   PORT=8080"
