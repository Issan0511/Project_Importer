#!/usr/bin/env python3
"""
このスクリプトは、下記案件テキストを JSON にまとめて
GAS ウェブアプリ（/exec）へ POST するだけの簡易テスト用です。
"""

import requests
import pprint

GAS_URL = "https://script.google.com/macros/s/AKfycbwtKz__23MLJMuo1-V1scLEyA7JOqcqk_vVpTqj_KLJFx7mcq--Xb8_mFANUQ3dy3gl/exec"

payload = {
    "overview":  "ドラッグストア日用品配送",
    "location":  "朝霞市＋新座市＋清瀬市＋東久留米＋練馬区（大泉エリア）",
    "startDate": "7/1〜",
    "vehicle":   "軽貨物",
    "headCount": "2名365",
    "operation": "月～土",
    "hours":     "09:00～21:00（4便制：09:00～12:30／13:30～15:30／15:30～17:30／17:30～21:00）",
    "amount":    "車建18,000円＋税",
    "cases":     "30件程度",
    "training":  "1日程度で完了（中長期でEV車両へ切替予定）"
}

def main() -> None:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    res = requests.post(GAS_URL, json=payload, headers=headers, timeout=30)

    print("=== HTTP status code ===")
    print(res.status_code)
    print("\n=== GAS response ===")
    try:
        pprint.pprint(res.json(), width=60, compact=True)
    except ValueError:
        # JSON 以外が返ってきたときはそのまま表示
        print(res.text)

if __name__ == "__main__":
    main()
