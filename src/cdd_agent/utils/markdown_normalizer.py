"""Markdown normalization for consistent rendering.

This module provides utilities to normalize markdown text from LLM responses
to ensure consistent rendering in the TUI. It handles common issues like:
- Underline-style headings (converting to ATX style)
- Excessive blank lines
- Broken code block markers
- Trailing whitespace
- Heading spacing

The normalizer is conservative - it only fixes obvious issues while preserving
intentional formatting choices (like list marker preference).
"""

import re


class MarkdownNormalizer:
    """Normalize markdown text for consistent rendering."""

    @staticmethod
    def normalize(text: str) -> str:
        """Apply all normalization rules to markdown text.

        Args:
            text: Raw markdown text (potentially from LLM)

        Returns:
            Normalized markdown text with consistent formatting

        Examples:
            >>> normalizer = MarkdownNormalizer()
            >>> text = "Heading\\n=======\\n\\n\\nContent"
            >>> normalizer.normalize(text)
            '# Heading\\n\\nContent'
        """
        if not text:
            return text

        # Apply normalization rules in order
        text = MarkdownNormalizer._convert_underline_headings(text)
        text = MarkdownNormalizer._remove_excessive_blank_lines(text)
        text = MarkdownNormalizer._fix_code_block_markers(text)
        text = MarkdownNormalizer._normalize_horizontal_rules(text)
        text = MarkdownNormalizer._fix_heading_spacing(text)
        text = MarkdownNormalizer._remove_trailing_whitespace(text)

        return text

    @staticmethod
    def _convert_underline_headings(text: str) -> str:
        """Convert underline-style headings to ATX style (# syntax).

        Converts:
            Heading
            =======
        To:
            # Heading

        And:
            Subheading
            ----------
        To:
            ## Subheading

        Args:
            text: Markdown text potentially containing underline-style headings

        Returns:
            Text with ATX-style headings
        """
        # Convert H1 style (text followed by ===)
        # Match: line of text, newline, line of equals signs
        text = re.sub(
            r"^(.+)\n=+\s*$",
            r"# \1",
            text,
            flags=re.MULTILINE,
        )

        # Convert H2 style (text followed by ---)
        # Match: line of text, newline, line of hyphens
        text = re.sub(
            r"^(.+)\n-+\s*$",
            r"## \1",
            text,
            flags=re.MULTILINE,
        )

        return text

    @staticmethod
    def _remove_excessive_blank_lines(text: str) -> str:
        """Remove excessive blank lines (more than 2 consecutive).

        Markdown typically uses single blank lines for paragraph breaks.
        Multiple blank lines are rarely intentional and make output look messy.

        Args:
            text: Markdown text

        Returns:
            Text with maximum 2 consecutive blank lines
        """
        # Replace 3+ newlines with exactly 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    @staticmethod
    def _fix_code_block_markers(text: str) -> str:
        """Fix broken code block markers (incomplete backticks).

        Ensures code blocks have proper opening and closing markers.
        This is a simple heuristic - just ensures even number of triple backticks.

        Args:
            text: Markdown text

        Returns:
            Text with balanced code block markers
        """
        # Count triple backtick occurrences
        triple_backticks = text.count('```')

        # If odd number, add one at the end (LLM probably got cut off)
        if triple_backticks % 2 == 1:
            text = text.rstrip() + '\n```\n'

        return text

    @staticmethod
    def _normalize_horizontal_rules(text: str) -> str:
        """Normalize horizontal rules to consistent style.

        Converts various HR styles (---, ***, ___) to standard --- for consistency.
        Only normalizes standalone HR lines (not part of underline headings).

        Args:
            text: Markdown text

        Returns:
            Text with normalized horizontal rules
        """
        # Match lines that are ONLY dashes, asterisks, or underscores (3+)
        # Must be on their own line with optional whitespace
        text = re.sub(
            r'^[\s]*(\*{3,}|_{3,})[\s]*$',
            r'---',
            text,
            flags=re.MULTILINE,
        )

        # Also normalize lines with dashes that are too long
        # (more than 10 dashes is excessive and may be decorative)
        text = re.sub(
            r'^[\s]*-{10,}[\s]*$',
            r'---',
            text,
            flags=re.MULTILINE,
        )

        return text

    @staticmethod
    def _fix_heading_spacing(text: str) -> str:
        """Ensure proper spacing around headings.

        Markdown convention:
        - Blank line before heading (except at start)
        - No extra blank line after heading

        Args:
            text: Markdown text

        Returns:
            Text with proper heading spacing
        """
        # Ensure blank line before headings (except at document start)
        # Match heading not preceded by blank line (but not at start)
        text = re.sub(
            r'([^\n])\n(#{1,6} )',
            r'\1\n\n\2',
            text,
        )

        # Remove multiple blank lines after headings
        text = re.sub(
            r'(#{1,6} .+)\n{3,}',
            r'\1\n\n',
            text,
        )

        return text

    @staticmethod
    def _remove_trailing_whitespace(text: str) -> str:
        """Remove trailing whitespace from each line.

        Trailing whitespace is rarely intentional and can cause issues
        with some markdown renderers.

        Args:
            text: Markdown text

        Returns:
            Text with trailing whitespace removed
        """
        # Remove trailing whitespace from each line
        lines = text.split('\n')
        lines = [line.rstrip() for line in lines]
        return '\n'.join(lines)


# Convenience function for quick access
def normalize_markdown(text: str) -> str:
    """Normalize markdown text (convenience function).

    Args:
        text: Raw markdown text

    Returns:
        Normalized markdown text

    Examples:
        >>> from cdd_agent.utils.markdown_normalizer import normalize_markdown
        >>> normalize_markdown("Heading\\n=======")
        '# Heading'
    """
    return MarkdownNormalizer.normalize(text)
