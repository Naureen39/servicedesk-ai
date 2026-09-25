"""Unit tests for Phase 6 item 4's spoken-form response formatting."""

from __future__ import annotations

from app.services.voice.spokenize import spoken_clock, spoken_digits, spoken_year, spokenize


def test_spoken_year_two_thousands():
    assert spoken_year(2000) == "two thousand"
    assert spoken_year(2005) == "two thousand five"


def test_spoken_year_regular_century_split():
    assert spoken_year(2019) == "twenty nineteen"
    assert spoken_year(2024) == "twenty twenty four"
    assert spoken_year(1998) == "nineteen ninety eight"
    assert spoken_year(1900) == "nineteen hundred"


def test_spoken_clock_examples_from_the_plan():
    assert spoken_clock(9, 30, "AM") == "nine thirty a m"
    assert spoken_clock(9, 0, "AM") == "nine o'clock a m"
    assert spoken_clock(9, 5, "PM") == "nine oh five p m"


def test_spoken_digits_reads_each_digit_separately():
    assert spoken_digits("4512") == "4 5 1 2"
    assert spoken_digits("614-555-0101") == "6 1 4 5 5 5 0 1 0 1"


def test_spokenize_converts_year_and_time_in_a_full_sentence():
    text = "Your appointment for a 2019 Honda Civic is at 09:30 AM."
    assert spokenize(text) == "Your appointment for a twenty nineteen Honda Civic is at nine thirty a m."


def test_spokenize_leaves_plain_text_unchanged():
    text = "Thanks for reaching out to Meridian Auto Group."
    assert spokenize(text) == text
