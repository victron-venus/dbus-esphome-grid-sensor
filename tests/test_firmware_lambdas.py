"""Analyze and execute the maintained C++ lambdas extracted from the real YAML."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_maintained_firmware_lambdas() -> None:
    """Check formula/threshold/diagnostic behavior with native memory instrumentation."""
    document = yaml.compose((ROOT / "esphome/grid-sensor.yaml").read_text())
    lambdas = []

    def collect(node: yaml.Node) -> None:
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                if key.value == "lambda":
                    lambdas.append(value.value)
                else:
                    collect(value)
        elif isinstance(node, yaml.SequenceNode):
            for value in node.value:
                collect(value)

    assert document is not None
    collect(document)
    assert len(lambdas) == 4, "Review new or removed firmware code in the native harness"
    compiler = shutil.which("clang++")
    assert compiler, "Install clang++ for firmware source analysis"
    declarations = """
    #include <cassert>
    #include <cmath>
    #include <cstdio>
    #include <limits>
    #include <string>
    struct Sensor { float state; };
    Sensor grid_current_adc{}, grid_power{}, grid_energy_forward{}, grid_energy_reverse{};
    #define id(name) name
    """
    functions = "\n".join(
        f"{kind} {name}({args}) {{\n{body}\n}}"
        for (kind, name, args), body in zip(
            [
                ("float", "power", ""),
                ("float", "reverse", "float x"),
                ("bool", "feed_in", ""),
                ("std::string", "diagnostics", ""),
            ],
            lambdas,
            strict=True,
        )
    )
    assertions = """
    int main() {
      grid_current_adc.state = 2; assert(power() == 460);
      grid_current_adc.state = -2; assert(power() == -460);
      grid_current_adc.state = NAN; assert(std::isnan(power()));
      assert(reverse(-1) == 1 && reverse(0) == 0 && reverse(1) == 0);
      grid_power.state = -50; assert(!feed_in());
      grid_power.state = -51; assert(feed_in());
      grid_current_adc.state = std::numeric_limits<float>::max();
      grid_energy_forward.state = std::numeric_limits<float>::max();
      grid_energy_reverse.state = -std::numeric_limits<float>::max();
      const auto text = diagnostics();
      assert(text.size() < 256 && text.find("Current:") == 0);
      grid_current_adc.state = NAN;
      assert(!diagnostics().empty());
    }
    """
    with tempfile.TemporaryDirectory(prefix="grid-firmware-source-") as directory:
        source = Path(directory) / "lambdas.cpp"
        source.write_text(declarations + functions + assertions)
        binary = Path(directory) / "lambdas"
        common = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror"]
        subprocess.run(
            [*common, "--analyze", "-Xanalyzer", "-analyzer-werror", str(source)],
            cwd=directory,
            check=True,
            timeout=30,
        )
        subprocess.run(
            [
                *common,
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                str(source),
                "-o",
                str(binary),
            ],
            check=True,
            timeout=30,
        )
        subprocess.run([str(binary)], check=True, timeout=10)
