"""Web UI 功能測試(需 Playwright):python tests/ui_smoke.py [輸出資料夾]。截圖 + 結果印到 stdout。"""
import os
import sys
import threading

from playwright.sync_api import sync_playwright

from plc_st.web import make_server

out = sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"
srv = make_server(port=0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/"
results = []


def ok(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_function("document.querySelectorAll('#profile option').length>3")
    ok("profiles loaded", True)
    pg.click("text=靜態檢查")
    pg.wait_for_selector("#chkout:not([hidden])")
    ok("check passes", "無問題" in pg.inner_text("#chkout"))
    pg.click("text=執行並繪製波形")
    pg.wait_for_function("document.getElementById('runst').textContent.includes('週期')")
    ok("virtual PLC run", "80" in pg.inner_text("#runst"))
    ok("waveform drawn", pg.evaluate("[...document.getElementById('wave').getContext('2d').getImageData(0,0,900,380).data].some(v=>v>0)"))
    pg.click("text=執行情境")
    pg.wait_for_selector("#tstout:not([hidden])")
    ok("scenario PASS", pg.inner_text("#tstout").strip() == "PASS")
    pg.set_input_files("#ragfile", {"name": "ton.md", "mimeType": "text/markdown",
                                     "buffer": "TON on-delay timer PT preset Q output 計時器".encode()})
    pg.click("text=加入索引")
    pg.wait_for_function("document.getElementById('ragst').textContent.includes('片段')")
    pg.select_option("#embsel", "hash")
    pg.fill("#ragq", "TON timer")
    pg.click("text=搜尋")
    pg.wait_for_selector("#ragout:not([hidden])")
    ok("RAG add+search", "ton.md" in pg.inner_text("#ragout"))
    pg.fill("#code", "PROGRAM X\nVAR a:INT; END_VAR\nb := 1;\nEND_PROGRAM")
    pg.click("text=靜態檢查")
    pg.wait_for_function("document.getElementById('chkout').textContent.includes('error')")
    ok("check reports error", "error" in pg.inner_text("#chkout"))
    pg.fill("#code", open("examples/motor.st", encoding="utf-8").read())
    with pg.expect_download() as dl:
        pg.click("text=匯出")
    ok("export PLCopen XML download", dl.value.suggested_filename == "program.xml"
       and "<pou" in open(dl.value.path(), encoding="utf-8").read())
    pg.select_option("#expfmt", "l5x")
    with pg.expect_download() as dl:
        pg.click("text=匯出")
    ok("export Rockwell L5X download", dl.value.suggested_filename.endswith(".L5X")
       and "<Routine" in open(dl.value.path(), encoding="utf-8").read())
    pg.select_option("#expfmt", "gxworks")
    with pg.expect_download() as dl:
        pg.click("text=匯出")
    ok("export GX Works3 download", dl.value.suggested_filename.endswith(".txt")
       and "Label Name" in open(dl.value.path(), encoding="utf-8").read())
    pg.click("text=產生 ST")
    pg.wait_for_function("document.getElementById('genout').className=='er'")
    ok("generate surfaces LLM error", True)
    ok("no JS errors", not errs)
    pg.reload()
    pg.wait_for_function("document.querySelectorAll('#profile option').length>3")
    pg.click("text=執行並繪製波形")
    pg.wait_for_function("document.getElementById('runst').textContent.includes('週期')")
    pg.click("text=靜態檢查")
    pg.click("text=執行情境")
    pg.wait_for_selector("#tstout:not([hidden])")
    pg.screenshot(path=f"{out}/web_ui.png", full_page=True)
    b.close()
srv.shutdown()
sys.exit(0 if all(r for _, r in results) else 1)
