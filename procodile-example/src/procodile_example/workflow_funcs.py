def fun_a(id: str) -> str:
    print("ran from main:::", id)
    return id


def fun_b(id: str) -> str:
    print("ran from second_step:::", id * 2)
    return id * 2


def fun_c(id: str) -> str:
    print("ran from third_step:::", id + "hello")
    return id + "hello"


def fun_d(id: str) -> str:
    print("ran from fourth_step:::", id + "world")
    return id + "world"


def fun_e(id: str, id2: str) -> tuple[str, str]:
    print("ran from fifth_step:::", id, id2)
    return id, id2


def fun_f(id: tuple[str, str], second_input: str) -> tuple[tuple[str, str], str]:
    print("ran from sixth_step:::", id)
    return id, second_input
