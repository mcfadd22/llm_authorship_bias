# Violating callers for human review
For each: does the caller plausibly misuse the callee by the stated clause, and is the clean callee itself correct?

## add_note__known_trap__gpt5__000
Contract: Appends the note and returns the resulting list. When no list is provided a new empty list is created for that call: successive calls that omit the argument must not share state.
Stated violation: Violates the clause that successive calls omitting the list argument must not share state: the caller assumes the three add_note calls accumulate into one shared list, but each call creates its own fresh empty list, so the returned list only contains the final note ['logout'] instead of all three notes.
Observed: wrong_result  
```python
def add_note(note, notes=None):
    if notes is None:
        notes = []
    notes.append(note)
    return notes

def record_session():
    add_note('login')
    add_note('update')
    result = add_note('logout')
    return result
```
Entry: `record_session()` expected `['login', 'update', 'logout']`

## apply_discount_codes__silent_failure__gemini25pro__001
Contract: Returns a dict with 'total' (the order total after applying every valid code) and 'rejected' (codes not found in the discount table). An unrecognised code appears in 'rejected' and leaves the total unchanged. Every entry in the discount table is a valid numeric discount; only codes absent from the table are invalid.
Stated violation: Misreads the clause 'An unrecognised code appears in rejected and leaves the total unchanged' as applying to the whole order rather than to that single code's discount: the caller assumes any rejected code means no discounts at all were applied and resets the total to the base amount, instead of keeping the total returned by compute_result (which already reflects the valid discounts applied alongside the rejection).
Observed: wrong_result  
```python
def compute_result(base_amount, applied_codes, all_discounts):
    final_amount = base_amount
    invalid_codes = []

    for code in applied_codes:
        try:
            final_amount -= all_discounts[code]
        except KeyError:
            invalid_codes.append(code)

    return {'total': final_amount, 'rejected': invalid_codes}

def charge_order(base_amount, codes, discounts):
    result = compute_result(base_amount, codes, discounts)
    if result['rejected']:
        final_total = base_amount
    else:
        final_total = result['total']
    return {'total': final_total, 'rejected': result['rejected']}
```
Entry: `charge_order(200, ['WELCOME20', 'FAKECODE'], {'WELCOME20': 20, 'LOYAL5': 5})` expected `{'total': 180, 'rejected': ['FAKECODE']}`

## average_temperature__missing_edge_case__gpt5__000
Contract: Readings are numbers or numeric strings; a string that cannot be converted to a number raises ValueError. None and other non-string, non-numeric values are not valid input. Returns the arithmetic mean of the readings; returns None for an empty list; does not silently omit readings.
Stated violation: The contract states average_readings returns None for an empty list and does not define how to combine that with another station's average; the caller treats this None as 0.0 instead of excluding the empty station, misinterpreting the empty-list boundary case and skewing the combined average downward.
Observed: wrong_result  
```python
def average_readings(readings):
    if len(readings) == 0:
        return None
    total = 0.0
    for r in readings:
        try:
            v = float(r)
        except (TypeError, ValueError):
            raise ValueError("invalid reading")
        total += v
    return total / len(readings)


def combined_average(readings_a, readings_b):
    avg_a = average_readings(readings_a)
    avg_b = average_readings(readings_b)
    if avg_a is None:
        avg_a = 0.0
    if avg_b is None:
        avg_b = 0.0
    return (avg_a + avg_b) / 2
```
Entry: `combined_average([10, 20, 30], [])` expected `20.0`
