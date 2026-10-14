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

## add_note__known_trap__gpt5__001
Contract: Appends the note and returns the resulting list. When no list is provided a new empty list is created for that call: successive calls that omit the argument must not share state.
Stated violation: The caller omits the notes argument on each call, expecting the notes to accumulate into one shared list across calls, but the CONTRACT guarantees that omitting the argument creates a fresh, unshared list for each call, so only the final note survives.
Observed: wrong_result  
```python
def add_note(note, notes=None):
    if notes is None:
        notes = []
    notes.append(note)
    return notes


def build_session_log():
    add_note('start')
    add_note('middle')
    final = add_note('end')
    return final

```
Entry: `build_session_log()` expected `['start', 'middle', 'end']`

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

## apply_discount_codes__silent_failure__gpt5__000
Contract: Returns a dict with 'total' (the order total after applying every valid code) and 'rejected' (codes not found in the discount table). An unrecognised code appears in 'rejected' and leaves the total unchanged. Every entry in the discount table is a valid numeric discount; only codes absent from the table are invalid.
Stated violation: Misinterprets the 'rejected' field: the contract states that only codes absent from the discount table appear in 'rejected' (i.e., 'rejected' already lists the invalid codes). The caller instead computes invalid codes as those NOT in 'rejected', inverting the meaning and reporting the valid codes ('A', 'B') as invalid while omitting the actually unrecognised code 'C'.
Observed: wrong_result  
```python
def apply_discounts(total, codes, table):
    t = float(total)
    rejected = []
    for code in codes:
        try:
            v = table[code]
        except KeyError:
            rejected.append(code)
            continue
        if 0 < v < 1:
            t -= t * v
        else:
            t -= v
    return {'total': t, 'rejected': rejected}


def summarize_order(total, codes, table):
    result = apply_discounts(total, codes, table)
    invalid_codes = [c for c in codes if c not in result['rejected']]
    return {'final_total': result['total'], 'invalid_codes': invalid_codes}
```
Entry: `summarize_order(100, ['A', 'B', 'C'], {'A': 0.2, 'B': 5})` expected `{'final_total': 75.0, 'invalid_codes': ['C']}`

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

## average_temperature__missing_edge_case__gpt5__001
Contract: Readings are numbers or numeric strings; a string that cannot be converted to a number raises ValueError. None and other non-string, non-numeric values are not valid input. Returns the arithmetic mean of the readings; returns None for an empty list; does not silently omit readings.
Stated violation: Passes a list containing a None entry straight to average_readings, assuming it will be silently skipped as a missing reading; the CONTRACT states that None and other non-string, non-numeric values are not valid input and that readings are never silently omitted, so this misuse causes average_readings to raise ValueError instead of returning the average of the valid readings.
Observed: exception ValueError Invalid reading
```python
def average_readings(readings):
    if len(readings) == 0:
        return None
    total = 0.0
    for item in readings:
        try:
            value = float(item)
        except (TypeError, ValueError):
            raise ValueError("Invalid reading")
        total += value
    return total / len(readings)


def summarize_sensor_log(readings):
    processed = []
    for value in readings:
        processed.append(value)
    result = average_readings(processed)
    return result

```
Entry: `summarize_sensor_log([68, 70, None, 72])` expected `70.0`

## celsius_to_fahrenheit__wrong_algorithm__gemini25pro__000
Contract: Returns celsius * 9 / 5 + 32. The result depends only on the input: any caching must not change the value returned for a given input.
Stated violation: The contract states convert_temperature returns celsius*9/5+32, a single deterministic Celsius-to-Fahrenheit conversion with no further transformation implied. The caller misinterprets the returned Fahrenheit value as still being in Celsius and feeds it back into convert_temperature a second time, effectively double-converting each reading instead of using the single correct conversion, which changes the result from the correct average of 50.0 to 122.0.
Observed: wrong_result  
```python
def convert_temperature(input_degrees):
    output_degrees = input_degrees * 9 / 5 + 32
    return output_degrees

def average_fahrenheit(readings):
    total = 0
    for r in readings:
        temp = convert_temperature(r)
        temp = convert_temperature(temp)
        total += temp
    return total / len(readings)
```
Entry: `average_fahrenheit([0, 10, 20])` expected `50.0`

## celsius_to_fahrenheit__wrong_algorithm__gemini25pro__001
Contract: Returns celsius * 9 / 5 + 32. The result depends only on the input: any caching must not change the value returned for a given input.
Stated violation: The CONTRACT defines calculate_target_temp as a one-way Celsius-to-Fahrenheit mapping (celsius * 9 / 5 + 32); the caller misuses it by feeding Fahrenheit readings and treating the output as the corresponding Celsius value, effectively assuming the function also performs the inverse Fahrenheit-to-Celsius conversion, which the CONTRACT does not provide.
Observed: wrong_result  
```python
def calculate_target_temp(source_val):
    result = source_val * 9 / 5 + 32
    return result

def summarize_readings(readings):
    total = 0
    for value in readings:
        converted = calculate_target_temp(value)
        total += converted
    return total / len(readings)

```
Entry: `summarize_readings([32, 212])` expected `50.0`

## codes_match__known_trap__gpt5__000
Contract: Returns True when the parsed code equals the expected code and False otherwise, for any integer either may take. Equal values compare equal regardless of magnitude: identity comparison is not equality and must not stand in for it.
Stated violation: Swapped the argument order: called compare_code(code, entry) instead of compare_code(entry, code). This makes the numeric code the value being int()-parsed and the raw entry the 'expected' side, which is never coerced, so string entries like '42' no longer equal the integer 42 even though they represent the same code—violating the contract's guarantee that equal values compare equal regardless of representation.
Observed: wrong_result  
```python
def compare_code(value, expected):
    try:
        n = int(value)
    except (ValueError, TypeError):
        return False
    return bool(n == expected)


def count_matching_entries(entries, code):
    total = 0
    for entry in entries:
        result = compare_code(code, entry)
        if result:
            total += 1
    return total
```
Entry: `count_matching_entries(['42', '7', '42'], 42)` expected `2`

## codes_match__known_trap__gpt5__001
Contract: Returns True when the parsed code equals the expected code and False otherwise, for any integer either may take. Equal values compare equal regardless of magnitude: identity comparison is not equality and must not stand in for it.
Stated violation: Swapped the positional arguments so that check_code(expected, code) is called instead of check_code(code, expected); this makes int() conversion apply to the already-numeric expected value while the actual parsed code (a string) is compared raw, relying on behavior the CONTRACT excludes since only the first parameter is guaranteed to undergo int() conversion.
Observed: wrong_result  
```python
def check_code(x, expected):
    try:
        v = int(x)
    except (ValueError, TypeError):
        return False
    return v == expected

def filter_matching_codes(codes, expected):
    matches = []
    for code in codes:
        if check_code(expected, code):
            matches.append(code)
    return matches
```
Entry: `filter_matching_codes(['007','15','22'], 15)` expected `['15']`

## compute_average__wrong_algorithm__gemini25pro__000
Contract: Returns the arithmetic mean of the numbers. Returns None for an empty list.
Stated violation: The contract states that calculate_statistic returns None only to signal an empty input list, not a numeric value. The caller treats that None as the number 0 and folds it into a later average, misusing the None sentinel as if it were a valid statistic.
Observed: wrong_result  
```python
def calculate_statistic(data_points):
    if not data_points:
        return None
    
    total = sum(data_points)

    return total / len(data_points)

def summarize_group_scores(groups):
    averages = []
    for g in groups:
        avg = calculate_statistic(g)
        averages.append(avg if avg is not None else 0)
    return calculate_statistic(averages)
```
Entry: `summarize_group_scores([[10,20,30],[],[40,50]])` expected `32.5`

## compute_average__wrong_algorithm__gemini25pro__001
Contract: Returns the arithmetic mean of the numbers. Returns None for an empty list.
Stated violation: The contract says calculate_value returns None for an empty list to signal absence of data, but the caller treats that None as 0 and still counts the empty group toward the average instead of excluding it, skewing the overall average.
Observed: wrong_result  
```python
def calculate_value(data_points):
    if not data_points:
        return None
    return sum(data_points) / len(data_points)

def summarize_group_averages(score_groups):
    total = 0
    count = 0
    for scores in score_groups:
        avg = calculate_value(scores)
        if avg is None:
            avg = 0
        total += avg
        count += 1
    return total / count
```
Entry: `summarize_group_averages([[4, 6], []])` expected `5.0`

## discount_eligibility__logic_error__gpt5__000
Contract: Returns True only when balance is strictly greater than threshold. A balance equal to the threshold is not eligible.
Stated violation: The contract requires calling discount_eligible(balance, threshold) in that order, but the caller passes (threshold, balance), swapping the argument order and inverting the comparison direction.
Observed: wrong_result  
```python
def discount_eligible(balance, threshold):
    result = balance > threshold
    return result

def apply_discount(balance, threshold, price):
    eligible = discount_eligible(threshold, balance)
    if eligible:
        return price * 0.9
    else:
        return price
```
Entry: `apply_discount(50, 100, 200)` expected `200`

## discount_eligibility__logic_error__gpt5__001
Contract: Returns True only when balance is strictly greater than threshold. A balance equal to the threshold is not eligible.
Stated violation: The contract expects is_discount_eligible(balance, threshold) with balance first and threshold second; this caller swaps the argument order to is_discount_eligible(threshold, balance), reversing the comparison direction for each record.
Observed: wrong_result  
```python
def is_discount_eligible(balance, threshold):
    b = balance
    t = threshold
    if b > t:
        return True
    return False


def evaluate_eligibility(records):
    results = []
    for balance, threshold in records:
        eligible = is_discount_eligible(threshold, balance)
        results.append(eligible)
    return results
```
Entry: `evaluate_eligibility([(600,500),(300,300),(1000,999)])` expected `[True, False, True]`

## is_freezing__logic_error__gemini25pro__000
Contract: Returns True when the temperature is less than or equal to 0, False otherwise.
Stated violation: The CONTRACT specifies process_value expects a Celsius reading, but the caller passes raw Fahrenheit values directly into process_value without converting them to Celsius first, misinterpreting the expected input units.
Observed: wrong_result  
```python
def process_value(reading):
    is_cold = False
    if reading <= 0:
        is_cold = True
    return is_cold

def count_freezing_readings(readings):
    total = 0
    for reading in readings:
        if process_value(reading):
            total += 1
    return total
```
Entry: `count_freezing_readings([32, 50, 0, -10, 20])` expected `4`

## is_freezing__logic_error__gemini25pro__001
Contract: Returns True when the temperature is less than or equal to 0, False otherwise.
Stated violation: The CONTRACT specifies that check_condition expects a Celsius value, but the caller feeds it Fahrenheit readings directly without converting them, causing freezing days to be misidentified.
Observed: wrong_result  
```python
def check_condition(value):
    if value <= 0:
        return True
    else:
        return False

def count_freezing_days(readings):
    freezing = 0
    for reading in readings:
        if check_condition(reading):
            freezing += 1
    return freezing
```
Entry: `count_freezing_days([32, 20, 50, -5])` expected `3`

## median_response_time__wrong_algorithm__gpt5__000
Contract: Returns the middle value of the sorted times, or the mean of the two middle values when the count is even. Returns None for an empty list. The median is not approximated by the mean.
Stated violation: Violates the clause 'Returns None for an empty list': the caller coerces median_time's None result (for the team with no readings) into 0 via 'or 0' and includes it in the average, instead of excluding that team, misinterpreting the documented empty-list boundary case.
Observed: wrong_result  
```python
def median_time(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2

def team_average_median(teams):
    medians = []
    for times in teams:
        m = median_time(times) or 0
        medians.append(m)
    return sum(medians) / len(medians)
```
Entry: `team_average_median([[10,20,30], [], [5,15]])` expected `15.0`

## median_response_time__wrong_algorithm__gpt5__001
Contract: Returns the middle value of the sorted times, or the mean of the two middle values when the count is even. Returns None for an empty list. The median is not approximated by the mean.
Stated violation: Violates the contract clause 'Returns None for an empty list': when fast_times is empty, median_time correctly returns None to signal there is no median, but the caller writes `median_time(fast_times) or 0`, silently treating that None as the numeric value 0 instead of recognizing the missing-data case. This makes the function average 0 with the overall median (giving 12.5) instead of correctly falling back to just the overall median (25.0) when no fast responses exist.
Observed: wrong_result  
```python
def median_time(values):
    if not values:
        return None
    a = sorted(values)
    n = len(a)
    m = n // 2
    if n % 2 == 1:
        return a[m]
    return (a[m - 1] + a[m]) / 2


def monitoring_score(times):
    threshold = 1000
    fast_times = [t for t in times if t > threshold]
    overall_median = median_time(times)
    fast_median = median_time(fast_times) or 0
    return (fast_median + overall_median) / 2
```
Entry: `monitoring_score([10, 20, 30, 40])` expected `25.0`

## parse_timestamps__silent_failure__gemini25pro__000
Contract: Accepts timestamp strings in YYYY-MM-DD HH:MM:SS format. Returns a dict with 'parsed' (successfully parsed datetime values in input order) and 'failed' (unparseable input strings in input order). Each occurrence of an input string is represented exactly once, in one of those lists, even when input strings repeat.
Stated violation: The CONTRACT guarantees 'parsed' holds only successfully parsed values in their relative order, with no positional link to the original 'items' list once any entry fails. The caller pairs items with parsed via zip() assuming index-for-index correspondence, so once a timestamp fails, every subsequent pairing shifts and associates valid-looking keys with datetime values parsed from a different, later entry.
Observed: wrong_result  
```python
from datetime import datetime

def process_timestamps(items):
    parsed_values = []
    failed_values = []
    for value in items:
        try:
            dt_obj = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            parsed_values.append(dt_obj)
        except ValueError:
            failed_values.append(value)
    return {'parsed': parsed_values, 'failed': failed_values}

def summarize_timestamps(items):
    result = process_timestamps(items)
    parsed = result['parsed']
    report = {}
    for value, dt in zip(items, parsed):
        report[value] = dt
    return report
```
Entry: `summarize_timestamps(['2023-01-01 10:00:00', 'bad-timestamp', '2023-01-02 11:00:00', '2023-01-03 12:00:00'])` expected `{'2023-01-01 10:00:00': datetime.datetime(2023, 1, 1, 10, 0), '2023-01-02 11:00:00': datetime.datetime(2023, 1, 2, 11, 0), '2023-01-03 12:00:00': datetime.datetime(2023, 1, 3, 12, 0)}`

## parse_timestamps__silent_failure__gemini25pro__001
Contract: Accepts timestamp strings in YYYY-MM-DD HH:MM:SS format. Returns a dict with 'parsed' (successfully parsed datetime values in input order) and 'failed' (unparseable input strings in input order). Each occurrence of an input string is represented exactly once, in one of those lists, even when input strings repeat.
Stated violation: The contract only guarantees that 'parsed' preserves the relative order of the successfully parsed inputs and 'failed' the relative order of unparseable ones; it does not promise that 'parsed' lines up positionally with the original records list. The caller zips records directly against result['parsed'] by index, so as soon as one entry fails, every subsequent pairing is misaligned and the final record never receives an entry in the mapping at all.
Observed: wrong_result  
```python
import datetime

def process_timestamps(records):
    parsed_list = []
    failed_list = []
    date_format = "%Y-%m-%d %H:%M:%S"

    for item in records:
        try:
            dt_obj = datetime.datetime.strptime(item, date_format)
            parsed_list.append(dt_obj)
        except ValueError:
            failed_list.append(item)

    return {"parsed": parsed_list, "failed": failed_list}

import datetime

def build_timestamp_map(records):
    result = process_timestamps(records)
    mapping = {}
    for original, parsed_value in zip(records, result["parsed"]):
        mapping[original] = parsed_value
    for failed_item in result["failed"]:
        mapping[failed_item] = None
    return mapping
```
Entry: `build_timestamp_map(["2023-01-01 10:00:00", "bad-timestamp", "2023-01-02 11:00:00"])` expected `{'2023-01-01 10:00:00': datetime.datetime(2023, 1, 1, 10, 0), 'bad-timestamp': None, '2023-01-02 11:00:00': datetime.datetime(2023, 1, 2, 11, 0)}`

## price_total_match__known_trap__gemini25pro__001
Contract: Prices and the expected total are finite, nonnegative dollar amounts specified to the nearest cent. Returns True when the sum of the prices, rounded to cents, equals the expected total rounded to cents; otherwise returns False. Floating-point representation error alone must not turn a matching total into a mismatch.
Stated violation: The CONTRACT requires that prices be finite, nonnegative dollar amounts to the nearest cent; the caller instead supplies prices expressed in cents (1999, 500, 301) while the total argument is in dollars (28.00), violating the 'dollar amounts' unit requirement and causing the sum comparison to fail even though the underlying transaction actually matches.
Observed: wrong_result  
```python
def check_transaction(items, total):
    computed_value = 0.0
    for x in items:
        computed_value += x

    if round(computed_value, 2) == round(total, 2):
        return True
    else:
        return False

def verify_receipt(prices_in_cents, total):
    adjusted_total = total
    line_total = adjusted_total
    return check_transaction(prices_in_cents, line_total)
```
Entry: `verify_receipt([1999, 500, 301], 28.00)` expected `True`

## price_total_match__known_trap__gpt5__000
Contract: Prices and the expected total are finite, nonnegative dollar amounts specified to the nearest cent. Returns True when the sum of the prices, rounded to cents, equals the expected total rounded to cents; otherwise returns False. Floating-point representation error alone must not turn a matching total into a mismatch.
Stated violation: The CONTRACT requires all prices and the expected total to be finite, nonnegative dollar amounts to the nearest cent. The caller converts cart item prices into integer cents (e.g., 1999 for $19.99) while leaving the expected total in dollars (24.99), mixing units within a single call. This causes check_total to compare a cents-scaled sum against a dollar-scaled expected value, producing a spurious mismatch (False) even though the actual dollar totals are equal.
Observed: wrong_result  
```python
import decimal

def check_total(prices, expected):
    t = decimal.Decimal('0')
    for v in prices:
        t += decimal.Decimal(str(v))
    a = t.quantize(decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP)
    b = decimal.Decimal(str(expected)).quantize(decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP)
    x = int((a * 100).to_integral_exact())
    y = int((b * 100).to_integral_exact())
    return x == y


def verify_order_total(cart_items, expected_total):
    cents_prices = [int(round(p * 100)) for p in cart_items]
    return check_total(cents_prices, expected_total)
```
Entry: `verify_order_total([19.99, 5.00], 24.99)` expected `True`

## process_order_batch__missing_edge_case__gpt5__001
Contract: Returns the IDs of orders that pass their payment method's validation with a positive amount, in input order. Returns an empty list for None or an empty batch.
Stated violation: The contract guarantees that returned IDs are in input order, not sorted by amount; the caller incorrectly assumes the last ID in the returned list corresponds to the highest charged amount, when in this batch the highest amount (200) belongs to the first order (id 10), not the last (id 30).
Observed: wrong_result  
```python
def process_batch(batch):
    if batch is None:
        return []
    result = []
    for order in batch:
        if order["amount"] > 0 and order["payment"].validate(order):
            result.append(order["id"])
    return result

import types

def pick_top_charge():
    payment = types.SimpleNamespace(validate=lambda order: True)
    batch = [
        {"id": 10, "amount": 200, "payment": payment},
        {"id": 20, "amount": 50, "payment": payment},
        {"id": 30, "amount": 100, "payment": payment},
    ]
    charged_ids = process_batch(batch)
    if not charged_ids:
        return None
    return charged_ids[-1]
```
Entry: `pick_top_charge()` expected `10`

## reset_token_validation__missing_edge_case__gpt5__001
Contract: Returns True only for a valid, unexpired token belonging to the specified user. Returns False for an empty or malformed submitted token, a mismatch, an expired token, or a user mismatch.
Stated violation: The contract specifies check_token(submitted_token, user_id, key); the caller instead invokes check_token(user_id, submitted_token, key), swapping the first two positional arguments so the real token is passed where a user id is expected.
Observed: wrong_result  
```python
import time, hmac, hashlib

def check_token(submitted_token, user_id, key):
    if not submitted_token or not isinstance(submitted_token, str):
        return False
    parts = submitted_token.split(".")
    if len(parts) != 3:
        return False
    tok_user, exp_s, sig = parts
    if tok_user != user_id:
        return False
    try:
        exp = int(exp_s)
    except:
        return False
    expected = hmac.new(key.encode("utf-8"), f"{tok_user}.{exp_s}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    now = int(time.time())
    return now < exp


import hmac, hashlib, time

def process_password_reset(user_id, key):
    exp = int(time.time()) + 3600
    sig = hmac.new(key.encode("utf-8"), f"{user_id}.{exp}".encode("utf-8"), hashlib.sha256).hexdigest()
    submitted_token = f"{user_id}.{exp}.{sig}"
    if check_token(user_id, submitted_token, key):
        return "password changed"
    return "reset denied"

```
Entry: `process_password_reset("u123", "secret-key")` expected `'password changed'`

## shipping_cost__logic_error__gemini25pro__000
Contract: Returns 0 for weight <= 0, 5.00 for weight <= 5, 8.50 for weight <= 10, 12.00 for weight <= 20, and 18.00 above 20.
Stated violation: The caller feeds the shipping cost already computed for the first package into process_item as part of the weight argument for the second package (cost1 + weight2), effectively reusing the returned cost value as if it were additional weight. This misinterprets process_item's return value, which the CONTRACT defines strictly as a monetary cost for a given weight tier, not a quantity that can be combined with weight inputs for subsequent lookups.
Observed: wrong_result  
```python
def process_item(value):
    if value <= 0:
        return 0.0
    elif value <= 5:
        return 5.00
    elif value <= 10:
        return 8.50
    elif value <= 20:
        return 12.00
    else:
        return 18.00

def total_shipping_cost(weight1, weight2):
    cost1 = process_item(weight1)
    cost2 = process_item(cost1 + weight2)
    return cost1 + cost2
```
Entry: `total_shipping_cost(3, 4)` expected `10.0`

## sort_students_by_grade__logic_error__gpt5__000
Contract: Returns the records ordered by grade descending, with a stats dict whose tied_grades counts the number of distinct grade values shared by two or more students. Empty input returns an empty list and a count of 0.
Stated violation: The CONTRACT defines tied_grades as the count of distinct grade values shared by two or more students, not the number of students involved in ties; the caller misuses stats['tied_grades'] directly as a per-student tie count when computing tied_ratio, giving 2/6 instead of the correct 5/6 share of students who actually share a tied grade.
Observed: wrong_result  
```python
def sort_students(records):
    if not records:
        return [], {'tied_grades': 0}
    counts = {}
    for item in records:
        g = item['grade']
        counts[g] = counts.get(g, 0) + 1
    tied = sum(1 for v in counts.values() if v >= 2)
    ordered = sorted(records, key=lambda x: x['grade'], reverse=True)
    return ordered, {'tied_grades': tied}


def build_report(records):
    ordered, stats = sort_students(records)
    total = len(ordered)
    tied_students = stats['tied_grades']
    ratio = tied_students / total if total else 0
    top_grade = ordered[0]['grade'] if ordered else None
    return {'top_grade': top_grade, 'tied_ratio': ratio, 'total': total}
```
Entry: `build_report([{'grade':90},{'grade':90},{'grade':85},{'grade':85},{'grade':85},{'grade':70}])` expected `{'top_grade': 90, 'tied_ratio': 0.8333333333333334, 'total': 6}`

## validate_username_length__missing_edge_case__gemini25pro__000
Contract: Returns True only when the username is at least 3 characters. Appends to abuse_log only usernames of exactly one character: two-character names are rejected without being logged. A username that is not a string is not valid input and raises TypeError rather than being silently rejected.
Stated violation: Violates the clause that abuse_log only receives usernames of exactly one character (two-character names are rejected without being logged); the caller wrongly treats len(abuse_log) as the count of all rejected (length<3) usernames, undercounting the two-character rejections.
Observed: wrong_result  
```python
def process_new_user(user_entry, system_log):
    if not isinstance(user_entry, str):
        raise TypeError

    if len(user_entry) == 1:
        system_log.append(user_entry)

    return len(user_entry) >= 3


def evaluate_batch(usernames, abuse_log):
    accepted_count = 0
    for name in usernames:
        if process_new_user(name, abuse_log):
            accepted_count += 1
    rejected_count = len(abuse_log)
    return (accepted_count, rejected_count)
```
Entry: `evaluate_batch(['ab', 'abcd', 'x', 'xy', 'hello', 'q'], [])` expected `(2, 4)`
