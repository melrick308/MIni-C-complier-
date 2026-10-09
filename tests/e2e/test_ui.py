"""Browser end-to-end tests. Run with:  python -m pytest -m e2e
Requires: pip install playwright  &&  python -m playwright install chromium
"""

import socket
import subprocess
import sys
import time
import urllib.request

import pytest

playwright = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.app:app", "--port", str(port),
                             "--log-level", "warning"])
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture()
def page(base_url):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        pg = context.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto(base_url)
        pg.evaluate("localStorage.clear()")
        pg.reload()
        pg.wait_for_selector(".phase.ok")
        yield pg
        browser.close()
        assert errors == [], errors


def open_tab(page, label):
    page.locator("#view-tabs .tab", has_text=label).first.click()


def load(page, example_id):
    page.select_option("#examples", example_id)
    page.wait_for_function("document.querySelector('#pipeline .summary').textContent.length > 0")
    page.wait_for_timeout(300)


def test_program_runs_and_prints(page):
    load(page, "07_fizzbuzz")
    assert "FizzBuzz" in page.inner_text("#bottom-output")
    assert "all phases passed" in page.inner_text("#pipeline")


def test_syntax_errors_show_problems_and_squiggles(page):
    load(page, "20_error_syntax")
    problems = page.inner_text("#bottom-problems")
    assert "Missing ';' after '5'" in problems
    assert page.locator(".mark-error").count() >= 3
    assert "stopped at the syntax phase" in page.inner_text("#pipeline")


def test_ir_and_cfg_views(page):
    load(page, "02_sum_to_n")
    open_tab(page, "TAC")
    assert "ifFalse" in page.inner_text("#view")
    open_tab(page, "CFG")
    page.wait_for_selector(".cfg-host svg", timeout=10000)
    open_tab(page, "AST")
    assert page.locator("svg.tree .node").count() > 10


def test_debugger_steps_and_shows_variables(page):
    load(page, "03_factorial_loop")
    open_tab(page, "Run")
    page.locator(".stepper button").nth(0).click()  # first
    for _ in range(4):
        page.locator(".stepper button").nth(3).click()  # next
    assert "5 / " in page.inner_text(".stepper .pos")
    assert page.locator(".line-exec").count() == 1
    assert "result" in page.inner_text(".frames")


def test_parse_steps_stepper(page):
    open_tab(page, "Parse Steps")
    page.locator(".stepper button").nth(0).click()
    assert "Program()" in page.inner_text(".stepper .now")
    page.locator(".stepper button").nth(3).click()
    assert page.locator("table.trace tr.current").count() == 1


def test_expression_mode_error_and_result(page):
    page.click("#mode-expression")
    page.fill("#expr", "a + * b")
    page.wait_for_selector("text=Syntax Error: Unexpected token '*'")
    assert "column 5" in page.inner_text("#view")
    page.fill("#expr", "a + b * (c - 2)")
    page.wait_for_selector("text=Result = 23")


def test_expression_parse_tree_builds_step_by_step(page):
    page.click("#mode-expression")
    page.fill("#expr", "a + b * c")
    page.wait_for_selector("text=Result")
    open_tab(page, "Parse Tree")
    page.locator(".stepper button").nth(0).click()
    assert page.locator("svg.tree .node.ghost").count() > 0
    page.locator(".stepper button").nth(4).click()  # last
    assert page.locator("svg.tree .node.ghost").count() == 0


def test_theme_toggle(page):
    before = page.get_attribute("html", "data-theme")
    page.click("#theme")
    assert page.get_attribute("html", "data-theme") != before
