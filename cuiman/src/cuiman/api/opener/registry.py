#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Callable

from .opener import Opener, OpenerContext


class OpenerRegistry:
    def __init__(self, *openers: Opener):
        self._openers = list(openers)

    def register(self, opener: Opener) -> Callable[[], None]:
        def unregister():
            self._openers.remove(opener)

        self._openers.append(opener)
        return unregister

    def open_result(self, ctx: OpenerContext) -> Opener:
        openers = list(self._openers)
        if not openers:
            raise RuntimeError("Job result opener registry is empty")

        errors = []
        for opener in openers:
            if opener.accept(ctx):
                try:
                    return opener.open_result(ctx)
                except Exception as e:
                    errors.append(e)

        if errors:
            first_error = errors[0]
            num_other_openers = len(errors) - 1
            msg_detail = ""
            if num_other_openers == 1:
                msg_detail = " (one other opener failed too)"
            elif num_other_openers > 1:
                msg_detail = f" ({num_other_openers} other openers failed too)"
            raise RuntimeError(
                f"Job result opener failure{msg_detail}: {first_error}"
            ) from first_error
        else:
            raise RuntimeError(f"No job result opener found for {ctx.job_results}")

    @classmethod
    def create_default(cls):
        return OpenerRegistry()
