# -*- coding: utf-8 -*-
import io
from html.parser import HTMLParser
from docxtpl import DocxTemplate
from odoo.exceptions import UserError

REQUIRED_PLACEHOLDERS = {
    "memo_reference",
    "from_display",
    "to_display",
    "memo_date",
    "subject",
    "memo_body",
}


class HTMLToPlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "div", "br", "li", "tr"):
            self.text_parts.append("\n")

    def get_text(self):
        return "".join(self.text_parts)


def convert_html_to_plain_text(html_content):
    if not html_content:
        return ""
    if "<" not in html_content and ">" not in html_content:
        return html_content
    parser = HTMLToPlainTextParser()
    parser.feed(html_content)
    lines = [line.strip() for line in parser.get_text().splitlines()]
    return "\n".join(line for line in lines if line)


class WordTemplateService:
    @staticmethod
    def validate_template(template_bytes):
        """Validate that all required placeholders exist in the Word document template."""
        if not template_bytes:
            raise UserError("The provided Word document template is empty.")

        template_io = io.BytesIO(template_bytes)
        try:
            doc_tpl = DocxTemplate(template_io)
            undeclared_vars = doc_tpl.get_undeclared_variables()
        except Exception as error:
            raise UserError(f"Failed to parse Word document template: {error}")

        missing = sorted(list(REQUIRED_PLACEHOLDERS - set(undeclared_vars)))
        if missing:
            bullet_list = "\n".join(f"• {item}" for item in missing)
            raise UserError(
                f"The active memo template is missing the following required placeholders:\n\n"
                f"{bullet_list}\n\n"
                f"Please update the active SharePoint memo template."
            )
        return True

    @staticmethod
    def render_template(template_bytes, context):
        """Render the DOCX template with the provided context dictionary and return DOCX bytes."""
        WordTemplateService.validate_template(template_bytes)

        raw_body = context.get("memo_body") or ""
        plain_body = convert_html_to_plain_text(raw_body)

        rendered_context = dict(context)
        rendered_context["memo_body"] = plain_body

        template_io = io.BytesIO(template_bytes)
        try:
            doc_tpl = DocxTemplate(template_io)
            doc_tpl.render(rendered_context)
            output_io = io.BytesIO()
            doc_tpl.save(output_io)
            return output_io.getvalue()
        except UserError:
            raise
        except Exception as error:
            raise UserError(f"The memo template could not be populated. Error: {error}")
