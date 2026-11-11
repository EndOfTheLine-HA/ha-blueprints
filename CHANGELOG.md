# Changelog

## Unreleased

- Irrigation zone flow check: baseline power and power per flow unit are now required, with no defaults,
  because they differ for every pump. The README's calibration example uses made-up numbers.

- Irrigation zone flow check: first version. Valve check from pump power, flow check from two power
  samples with a linear conversion, per-zone expected flow, percent and minimum tolerances, optional
  averaged power sensor, optional flow conditions, and custom alert actions with a persistent
  notification by default.
