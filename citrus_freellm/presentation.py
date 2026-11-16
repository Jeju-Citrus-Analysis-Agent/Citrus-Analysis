"""Keep verified conclusions first and full evidence available in every surface."""
SUMMARY_HEADER = '**결론**'
DETAILS_HEADER = '**세부 설명**'


def result_first(summary, details):
    return f'{SUMMARY_HEADER}\n\n{summary.strip()}\n\n{DETAILS_HEADER}\n\n{details.strip()}'


def split_answer(answer):
    for summary_header, details_header in ((SUMMARY_HEADER, DETAILS_HEADER), ('**결과 요약**', '**자세한 내용**')):
        if answer.startswith(summary_header + '\n'):
            summary, separator, details = answer.partition('\n\n' + details_header + '\n\n')
            if separator:
                return summary.replace(summary_header, SUMMARY_HEADER, 1), DETAILS_HEADER + '\n\n' + details
    return answer, ''
