# Contract-blind code review: three options

We need one check on the item bank that only you can do, because you have not seen the
specifications the code was written against. The question for each function: **from the
one-sentence description and the code alone, can you tell what is wrong with it?** Judge models
see exactly that and no more, so an item only works if its problem is visible from there.

**Before and during the review, please open only the sheet file.** Other files in the repo
(configs, item data, other review sheets, design and status docs) describe the intended
problems, and seeing them would undo the point of your pass. Afterwards, anything is fine.

## Options

Pick whichever fits your time. Each is a legitimate choice. They differ in what we can say in
the write-up.

**A. Full pass: `analysis/aim_only_review.html`, 124 functions.** Roughly 3–4 hours.
Every eligibility decision then has a human contract-blind account behind it. This is the
strongest version.

**B. Subset: `analysis/aim_only_review_selection.html`, 66 functions.** Roughly 2 hours.
Chosen by a fixed, recorded procedure, which we'll explain once you've finished (knowing it in
advance would bias the answers). A model has already done a blind pass on all 124, so this is a
human check on part of that. If your answers show a problem in any category, the plan is to
extend the review to that whole category.

**C. No further pass: call the banks sufficiently vetted.** No time from you. The banks have
had a full specification-based review from me and a contract-blind pass by a model. We would
either decide each item's flag between us from those, or keep the calls from my review; either
way no human contract-blind account would be behind them, and the write-up would say so.

Whichever you pick, no item is removed from the banks: every item is run, and items whose
problem isn't visible from the description are set aside in the analysis by a rule we have
already fixed.

## Doing A or B

Open the file in a browser. For each function, say whether the code does something wrong. If
it does, give the input where it goes wrong, what it does, and what it should do, in your own
words, and say whether the description itself establishes that or only a convention or an
ambiguous boundary does. "No" is a perfectly good answer. The instructions are at the top of
the sheet.

Answers save in the browser as you go, so you can stop and come back in the same browser. If
you start on B and decide to do A, open the full sheet in the same browser: your answers carry
over. When finished, click **Export CSV** and send us `aim_only_review.csv`.

Whichever option you choose, tell us, so it can be recorded.
