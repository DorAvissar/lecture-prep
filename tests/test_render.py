from lecture_prep.web.render import render_inline, render_markdown


def test_latin_runs_are_isolated_inside_hebrew():
    assert render_inline("ההבדל בין Java ל-C++ גדול") == ("ההבדל בין <bdi>Java</bdi> ל-<bdi>C++</bdi> גדול")


def test_code_spans_become_code_and_are_escaped():
    assert render_inline("קריאה ל-`a < b` כאן") == "קריאה ל-<code>a &lt; b</code> כאן"


def test_bold_wraps_isolated_text():
    assert render_inline("**memory leak** הוא באג") == "<b><bdi>memory leak</bdi></b> הוא באג"


def test_html_in_text_is_escaped():
    assert "<script>" not in render_inline("<script>alert(1)</script>")


def test_headings_paragraphs_and_bullets():
    markdown = "### כותרת\nשורה אחת\nשורה שתיים\n\n- ראשון\n- שני"

    assert render_markdown(markdown) == (
        "<h3>כותרת</h3>\n<p>שורה אחת<br>שורה שתיים</p>\n<ul><li>ראשון</li><li>שני</li></ul>"
    )


def test_fenced_code_is_left_to_right_and_untouched():
    markdown = "לפני\n```cpp\nint* p = new int(8);\n```\nאחרי"

    assert render_markdown(markdown) == (
        '<p>לפני</p>\n<pre dir="ltr"><code>int* p = new int(8);</code></pre>\n<p>אחרי</p>'
    )
