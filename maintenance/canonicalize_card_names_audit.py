from maintenance import canonicalize_card_names


def run() -> None:
    canonicalize_card_names.audit()
