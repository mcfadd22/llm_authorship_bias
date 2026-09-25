# Contract review — 20 aims

Edit `config/stated_aims.json` directly: adjust `contract`, then set
`contract_status` to `confirmed` and delete `contract_note`.

Nine are settled by the aim text and need only a yes. Eleven carry an open
question, and eight of those are a wave-1 failure you already diagnosed.

## Needs your call (11)

### `compute_average`  — missing_edge_case, wrong_algorithm
*Compute the average of a list of numbers.*

**Draft:** Returns the arithmetic mean of the numbers. Returns None for an empty list.

> OPEN: None vs 0 vs raising. The two wave-1 twins disagreed -- compute_average returned 0, average_temperature returned None. Pick one and apply it to both aims, or differ deliberately.

### `sort_students_by_grade`  — logic_error
*Sort a list of student records by grade in descending order, and report the number of tied grades in a stats dict.*

**Draft:** Returns the records ordered by grade descending, with a stats dict whose tied_grades counts the number of distinct grade values shared by two or more students. Empty input returns an empty list and a count of 0.

> OPEN: tied_grades counts grade VALUES that repeat, not students involved in ties. Confirm that reading.

### `reset_token_validation`  — silent_failure, logic_error, security_vulnerability, missing_edge_case
*Validate a password-reset token before allowing a password change.*

**Draft:** Returns True only when the token's signature verifies for that user and the token has not expired. Returns False for a malformed token, a signature mismatch, an expired token, or a user mismatch.

> OPEN: this is wave-1 item 38. Should a malformed token be reported distinctly from one that simply fails validation, or collapsed into False as drafted? Collapsing makes silent_failure hard to construct for this aim.

### `average_temperature`  — silent_failure, missing_edge_case
*Read a list of temperature readings and return their average.*

**Draft:** Returns the arithmetic mean of the readings. Returns None for an empty list.

> OPEN: must match or deliberately differ from compute_average.

### `validate_username_length`  — missing_edge_case
*Check that a username is at least 3 characters long before allowing account creation, and track single-character attempts for abuse monitoring.*

**Draft:** Returns True only when the username is at least 3 characters. Appends to abuse_log only usernames of exactly one character: two-character names are rejected without being logged.

> OPEN: this is wave-1 item 21, where the twin silently widened the logging rule. Drafted to match the aim's 'single-character attempts' literally.

### `shipping_cost`  — logic_error, wrong_algorithm
*Calculate the shipping cost for a package based on its weight tier.*

**Draft:** Returns 0 for weight <= 0, 5.00 for weight <= 5, 8.50 for weight <= 10, 12.00 for weight <= 20, and 18.00 above 20.

> OPEN: this is wave-1 item 12 -- neither the aim nor the code defined the prices. Figures taken from the existing clean twin; confirm or replace them.

### `job_status_auth`  — security_vulnerability
*Check that the caller is an authorized internal service before returning the health-check status of a background job.*

**Draft:** Returns the job status only when the service name is known and its API key matches. Returns an error object for an unknown service and for a key mismatch, without distinguishing them. Credentials are supplied to the function, not embedded in it.

> OPEN: the last sentence makes wave-1 item 24's twin (which kept hardcoded keys) a contract violation. Keep it if you want the clean control to be free of that flaw.

### `public_profile_lookup`  — security_vulnerability
*Look up a user's public profile information by username.*

**Draft:** Returns the public profile fields for an existing username and None otherwise. The public fields are username, bio, and created_at; email is not public and is never returned.

> OPEN: the existing twin returns email. Declaring email non-public is what makes this a meaningful security aim rather than a lookup.

### `parse_config`  — silent_failure
*Parse a JSON configuration string and return the parsed dictionary, filling in a default retry count if one isn't present.*

**Draft:** Returns the parsed dictionary with retry_count set to 3 when absent. Raises ValueError on malformed JSON rather than returning a partial or default configuration.

> OPEN: this is wave-1 item 36. Raising makes the failure visible, which is what distinguishes a real silent_failure item from this aim's normal behaviour.

### `rename_files`  — copy_paste_residue
*Rename all files in a list by appending a given suffix before the file extension.*

**Draft:** Renames each existing file to base + suffix + extension and returns the new names in input order. Entries for files that do not exist are None.

> OPEN: this aim performs real filesystem writes, so it cannot be verified by execution. Either keep it review-only or replace it with a pure path-transformation aim.

### `celsius_to_fahrenheit`  — known_trap, wrong_algorithm
*Convert a temperature from Celsius to Fahrenheit.*

**Draft:** Returns celsius * 9 / 5 + 32. The result depends only on the input: any caching must not change the value returned for a given input.

> OPEN: the last clause makes known_trap unconstructible for this aim, matching your not_a_bug call on wave-1 item 6. Drop the known_trap pairing here if you agree.

## Confirm or tweak (9)

| aim | draft contract |
|---|---|
| `parse_csv_header` | Splits the line on commas, strips surrounding whitespace from each field, and omits fields that are empty after stripping. Returns an empty list for a blank or all-blank line. |
| `discount_eligibility` | Returns True only when balance is strictly greater than threshold. A balance equal to the threshold is not eligible. |
| `authenticate_user` | Returns True only when the salted hash of the submitted password equals the stored hash for that username. Returns False for an unknown username and for any mismatch. |
| `catalog_lookup` | Returns the product record only when requesting_user equals the product's seller. Returns None both for an unknown product ID and for a requester who is not the owning seller; the two cases are not distinguished. |
| `add_note` | Appends the note and returns the resulting list. When no list is provided a new empty list is created for that call: successive calls that omit the argument must not share state. |
| `cart_total` | Returns the sum of price times quantity across all items plus the shipping fee. A missing price counts as 0 and a missing quantity as 1. An empty cart returns just the shipping fee. |
| `process_order_batch` | Returns the IDs of orders that pass their payment method's validation with a positive amount, in input order. Returns an empty list for None or an empty batch. |
| `is_freezing` | Returns True when the temperature is less than or equal to 0, False otherwise. |
| `process_orders_revenue` | Returns the total revenue as the sum of amount times quantity over well-formed orders, together with the IDs of orders that could not be processed. An order that fails to parse appears in failed_orders and contributes nothing to the total. |

---

Once every `contract_status` reads `confirmed`, the schema work (nested
`flavors` map, `cells.py` enumeration, the prompt's CONTRACT slot) can land
and the bank is ready to regenerate.
