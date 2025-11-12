"""Custom Markdown renderer with left-aligned headings without underlines.

This module provides a custom Markdown renderer that extends Rich's Markdown
but overrides the heading alignment to use left-align instead of center,
and removes underlines from headings.
"""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading as RichHeading
from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from rich.style import Style


class LeftAlignedHeading(RichHeading):
    """Custom Heading that uses left alignment and no underlines."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render the heading with left alignment and no underline.

        Args:
            console: Rich console instance
            options: Console rendering options

        Yields:
            Renderable objects
        """
        text = self.text
        # Override Rich's default center alignment with left
        text.justify = "left"

        # Remove underline from the text style
        # Get the current style and create a new one without underline
        for i in range(len(text.spans)):
            span = text.spans[i]
            if span.style:
                # Create new style without underline
                current_style = span.style if isinstance(span.style, Style) else Style.parse(str(span.style))
                new_style = Style(
                    color=current_style.color,
                    bgcolor=current_style.bgcolor,
                    bold=current_style.bold,
                    dim=current_style.dim,
                    italic=current_style.italic,
                    underline=False,  # Remove underline
                    blink=current_style.blink,
                    blink2=current_style.blink2,
                    reverse=current_style.reverse,
                    conceal=current_style.conceal,
                    strike=current_style.strike,
                    underline2=False,  # Remove double underline too
                    frame=current_style.frame,
                    encircle=current_style.encircle,
                    overline=current_style.overline,
                    link=current_style.link,
                )
                text.spans[i] = span.__class__(span.start, span.end, new_style)

        if self.tag == "h1":
            # For h1, we still show it but left-aligned without underline
            yield Text("")  # Blank line before
            yield text
        else:
            # Styled text for h2 and beyond
            if self.tag == "h2":
                yield Text("")  # Blank line before h2
            yield text


class LeftAlignedMarkdown(RichMarkdown):
    """Custom Markdown renderer with left-aligned headings and no underlines.

    This extends Rich's Markdown class but uses LeftAlignedHeading
    for heading rendering instead of the default centered and underlined headings.
    """

    # Map element tags to custom element classes
    elements = RichMarkdown.elements.copy()

    # Override the heading_open element with our custom left-aligned version
    elements["heading_open"] = LeftAlignedHeading
