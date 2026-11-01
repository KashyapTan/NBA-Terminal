"""Installed Firefox extension smoke against fantasy_e2e_server only.

Start `uv run python tests/fantasy_e2e_server.py`, then run
`uv run --with selenium python tests/espn_extension_browser_smoke.py`.
A fresh disposable profile is created by WebDriver. No normal profile is opened.
The shipped ZIP/background/content scripts and all local HTTP routes are real.
Only the provider cookie contents and external ESPN/NBA transport are synthetic.
Headless toolbar popup frames are not WebDriver-addressable: the shipped popup
is also opened in a tab for the real permission prompt. After consent, BiDi sends
its actual enable command from that popup while the local app tab is active.
No browser permission preference or production manifest is bypassed/modified.
"""

import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import urlopen

import websocket
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[1]


def run(base, binary, geckodriver):
    with urlopen(base + "/__test__/fantasy-fixture") as response:
        assert json.load(response) == {"synthetic": True}, "Use the test-only fixture server"
    options = Options()
    options.binary_location = binary
    options.add_argument("-headless")
    options.set_capability("webSocketUrl", True)
    # Chrome-context access is solely for automating the disposable browser's
    # real toolbar and permission UI, never for reading user profiles/cookies.
    service = Service(executable_path=geckodriver, service_args=["--allow-system-access", "--log", "error"])
    driver = webdriver.Firefox(options=options, service=service)
    ws = None
    try:
        driver.implicitly_wait(5)
        driver.install_web_extension(str(ROOT / "nba_terminal/browser_extension/dist/firefox.zip"), permanent=False)
        driver.get(base + "/fantasy")
        main = driver.current_window_handle
        driver.find_element("css selector", 'input[name="league"]').send_keys("123")
        driver.find_element("css selector", 'input[name="season"]').send_keys("2027")
        driver.find_element("xpath", '//button[text()="Connect ESPN"]').click()
        driver.set_context("chrome")
        driver.find_element("id", "unified-extensions-button").click()
        driver.find_element("id", "espn-session_nba-terminal_local-BAP").click()
        wait = WebDriverWait(driver, 15)
        popup_url = wait.until(
            lambda d: d.execute_script(
                'return [...document.querySelectorAll("browser")].find(x=>'
                'x.currentURI?.spec.endsWith("popup.html"))?.currentURI.spec'
            )
        )
        driver.execute_script(
            'document.getElementById("customizationui-widget-panel")?.hidePopup();'
            "gBrowser.addTab(arguments[0],{inBackground:true,"
            "triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()})",
            popup_url,
        )
        ws = websocket.create_connection(driver.capabilities["webSocketUrl"], suppress_origin=True, timeout=15)
        serial = 0

        def call(method, params):
            nonlocal serial
            serial += 1
            ws.send(json.dumps({"id": serial, "method": method, "params": params}))
            while True:
                result = json.loads(ws.recv())
                if result.get("id") == serial:
                    assert result["type"] == "success", result
                    return result["result"]

        def popup_context():
            return next(
                (c["context"] for c in call("browsingContext.getTree", {})["contexts"] if c["url"] == popup_url), None
            )

        popup = wait.until(lambda _: popup_context())
        driver.set_context("content")
        driver.switch_to.window(popup)
        driver.find_element("id", "enable").click()
        driver.set_context("chrome")
        wait.until(lambda d: d.find_element("id", "addon-webext-permissions-notification"))
        # Honor the browser's short anti-clickjacking delay before UI acceptance.
        time.sleep(1)
        driver.execute_script(
            'document.querySelector("#notification-popup .popup-notification-primary-button").click()'
        )
        driver.set_context("content")
        driver.switch_to.window(main)

        def extension(expression):
            result = call(
                "script.evaluate", {"expression": expression, "target": {"context": popup}, "awaitPromise": True}
            )
            assert result["type"] == "success", result
            return result["result"].get("value")

        assert extension('browser.permissions.contains({permissions:["cookies"],origins:["https://*.espn.com/*"]})')
        # Seed only the two synthetic test credentials through the REAL browser
        # cookie API after permission, before origin consent/first cookie read.
        assert extension(
            'Promise.all([browser.cookies.set({url:"https://www.espn.com/",name:"SWID",'
            'value:"fixture-owner-0001",secure:true,httpOnly:true}),browser.cookies.set('
            '{url:"https://www.espn.com/",name:"espn_s2",value:"synthetic-only-cookie",'
            "secure:true,httpOnly:true})]).then(()=>true)"
        )
        extension(
            "(async()=>{const [t]=await browser.tabs.query({active:true,currentWindow:true});"
            'await browser.runtime.sendMessage({type:"enable",tabId:t.id});'
            'await browser.tabs.sendMessage(t.id,{type:"cookie_changed"});return true})()'
        )
        wait.until(lambda d: "Connected · private access" in d.find_element("css selector", ".league-dashboard").text)
        Select(driver.find_element("css selector", 'select[aria-label="Your ESPN team"]')).select_by_value("1")
        wait.until(
            lambda d: "Current opponent: Fixture Team 2" in d.find_element("css selector", ".league-dashboard").text
        )

        def status():
            return driver.execute_async_script('fetch("/api/fantasy/espn/status").then(r=>r.json()).then(arguments[0])')

        initial = status()
        assert initial["ownership_verified"] and initial["team_id"] == 1
        extension(
            'browser.cookies.set({url:"https://www.espn.com/",name:"espn_s2",'
            'value:"synthetic-rotated-cookie",secure:true,httpOnly:true}).then(()=>true)'
        )
        # No manual refresh/notify here: the installed background cookie listener
        # must trigger isolated relay renewal and retain backend-owned team.
        wait.until(lambda _: status().get("expires_at") != initial["expires_at"])
        assert status()["team_id"] == 1
        assert driver.execute_script(
            'return !JSON.stringify(localStorage).includes("synthetic-") &&'
            '!document.documentElement.outerHTML.includes("synthetic-only-cookie") &&'
            '!document.cookie.includes("nba_espn_session")'
        )
        driver.find_element("xpath", '//button[text()="Disconnect ESPN"]').click()
        wait.until(lambda _: not status()["connected"])
        extension(
            'browser.cookies.set({url:"https://www.espn.com/",name:"espn_s2",'
            'value:"synthetic-disconnected-cookie",secure:true,httpOnly:true}).then(()=>true)'
        )
        time.sleep(2.5)
        assert not status()["connected"]
        print(
            json.dumps(
                {
                    "browser": "Firefox " + driver.capabilities["browserVersion"],
                    "installed_zip": True,
                    "real_permission_prompt": True,
                    "real_cookie_read_and_same_origin_adoption": True,
                    "cookie_change_renewal_retains_team": True,
                    "disconnect_stops_reconnect": True,
                    "external_transport": "synthetic ESPN/NBA",
                    "live_private_account_test": False,
                }
            )
        )
    finally:
        if ws:
            ws.close()
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8197")
    parser.add_argument("--firefox", default="/Applications/Firefox.app/Contents/MacOS/firefox")
    parser.add_argument("--geckodriver", default=os.environ.get("GECKODRIVER"))
    args = parser.parse_args()
    run(args.base_url.rstrip("/"), args.firefox, args.geckodriver)
