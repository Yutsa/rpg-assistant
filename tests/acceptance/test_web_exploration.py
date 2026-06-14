from __future__ import annotations

from playwright.sync_api import Page, expect


def test_campaign_list_shows_momie(page: Page) -> None:
    expect(page.get_by_role("heading", name="Campagnes")).to_be_visible()
    expect(page.get_by_role("link", name="Momie")).to_be_visible()


def test_document_picker_and_explorer(page: Page) -> None:
    page.get_by_role("link", name="Momie").click()
    expect(page.get_by_role("heading", name="Documents — momie")).to_be_visible()
    page.get_by_role("link", name="test.pdf").click()

    expect(page.get_by_role("heading", name="Sections")).to_be_visible()
    expect(page.get_by_role("button", name="Intro")).to_be_visible()
    expect(page.get_by_text("Hello adventurer")).to_be_visible()


def test_chunk_detail_and_stat_block_link(page: Page) -> None:
    page.get_by_role("link", name="Momie").click()
    page.get_by_role("link", name="test.pdf").click()
    page.get_by_text("Hello adventurer").click()

    expect(page.get_by_role("heading", name="Chunk")).to_be_visible()
    expect(page.get_by_text("Hello adventurer", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Voir la source")).to_be_visible()


def test_stat_blocks_index_and_detail(page: Page) -> None:
    page.get_by_role("link", name="Momie").click()
    page.get_by_role("link", name="test.pdf").click()
    page.get_by_role("link", name="Fiches stats").click()

    expect(page.get_by_role("heading", name="Fiches COF2")).to_be_visible()
    page.get_by_role("link", name="Gobelin").click()

    expect(page.get_by_role("heading", name="Gobelin")).to_be_visible()
    expect(page.get_by_text("NC 1")).to_be_visible()
    expect(page.get_by_role("rowheader", name="FOR")).to_be_visible()
