"""Keep verified conclusions first and full evidence available in every surface."""
SUMMARY_HEADER = '**결론**'
DETAILS_HEADER = '**세부 설명**'


def number(value, signed=False):
    """18044.0 reads as 18,044 and 16.5 as 16.5: no padded decimal places."""
    text = f"{value:{'+' if signed else ''},.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def result_first(summary, details):
    return f'{SUMMARY_HEADER}\n\n{summary.strip()}\n\n{DETAILS_HEADER}\n\n{details.strip()}'


def split_answer(answer):
    for summary_header, details_header in ((SUMMARY_HEADER, DETAILS_HEADER), ('**결과 요약**', '**자세한 내용**')):
        if answer.startswith(summary_header + '\n'):
            summary, separator, details = answer.partition('\n\n' + details_header + '\n\n')
            if separator:
                return summary.replace(summary_header, SUMMARY_HEADER, 1), DETAILS_HEADER + '\n\n' + details
    return answer, ''
