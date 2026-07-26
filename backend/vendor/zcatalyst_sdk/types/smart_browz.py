from typing import Literal, TypedDict, Union


PdfFormats = Literal[
    'Letter', 'Legal', 'Tabloid', 'Ledger',
    'A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6'
]

PdfMargin = TypedDict('PdfMargin', {
    'top': str,
    'bottom': str,
    'left': str,
    'right': str
}, total=False)


class PdfOptions(TypedDict, total=False):
    scale: Union[int,str]
    display_header_footer: bool
    header_template: str
    footer_template: str
    print_background: bool
    landscape: bool
    page_ranges: Union[int,str]
    format: PdfFormats
    width: Union[int,str]
    height: Union[int,str]
    margin: PdfMargin


CssContent = TypedDict('CssContent', {
    'content': str
})

CssUrl = TypedDict('CssUrl', {
    'url': str
})

JsContent = TypedDict('JsContent', {
    'content': str
})

JsUrl = TypedDict('JsUrl', {
    'url': str
})

PdfViewPort = TypedDict('PdfViewPort', {
    "width": Union[int,str],
    "height": Union[int,str]
})


class PdfPageOptions(TypedDict, total=False):
    css: Union[CssContent, CssUrl]
    js: Union[JsContent, JsUrl] # pylint: disable=invalid-name
    viewport: PdfViewPort
    javascript_enabled: bool


class ScreenShotOptions(TypedDict, total=False):
    type: Literal['jpeg', 'png']
    quality: Union[int, str]
    full_page: bool
    omit_background: bool
    capture_beyond_viewport: bool


class ScreenShotPageOptions(TypedDict):
    device: str


class NavigationOptions(TypedDict, total=False):
    timeout: Union[int,str]
    wait_until: Literal['load', 'domcontentloaded', 'networkidle0', 'networkidle2']

class OutputOptions(TypedDict):
    output_type: Literal['pdf', 'screenshot']
