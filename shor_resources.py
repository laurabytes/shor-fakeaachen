"""Compatibilidade do código-fonte de referência com os módulos do projeto."""

import os
import platform

from resources import check_resources, memory_budget_mb


def hardware_info():
    return {
        "system": platform.system(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
