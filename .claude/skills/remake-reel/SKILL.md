---
name: remake-reel
description: Turn a reel that went viral into a new script on the user's own topic, keeping what made it work - the hook pattern, the beats, the pacing and the call to action - then hand it to make-reel. Use when the user pastes a reel's transcript or link, or drops a saved reel in My References/, and says "remake this", "break this down", "why did this work", "write my version", "use this as a reference", or asks how to find reels worth remaking.
---

# Remake a reel

Proven reels are the best starting point: their structure already worked. Keep the structure; change the words, the topic and anything that isn't true for the user. The prompts behind each step are in `references/prompts.md`, written so they also work on their own in any Claude chat.

## 1. Get the words

- **Pasted transcript:** use it.
- **A video file** (the user saved it in `My References/` or `My Footage/`): transcribe it with `uv run --project kit kit/run.py talk transcribe "My References/<file>"` and read `work/<name>/transcript.txt`. Also look at a contact sheet (`talk sheet`) to see what's on screen.
- **Only a link:** don't download it. Ask the user to paste the words (Instagram shows a transcript under many reels) or save the video to `My References/` themselves.
- **"How do I find good ones?":** give them the finding guide from `references/prompts.md` (outliers: reels with at least 5 times the views of that account's usual reel).

## 2. Break it down

Write `work/<name>-breakdown.md` using the breakdown prompt: the hook and why it stops the scroll, each beat line by line with its job, the turn, the payoff, the call to action, the pacing (words, seconds, lines), and what's on screen for each beat. End with "why it works" in three plain sentences.

## 3. Ask one question

In one message: "What's your topic or offer, and do you want a comment keyword at the end (like SKILL or GUIDE)?" If they already said, skip this.

## 4. Write the new script

Use the rewrite prompt. Rules:

- Same skeleton: same number of beats, same order, same hook pattern, about the same length.
- Their topic and their words. Never copy lines, footage or music.
- Keep only claims that are true for them. If the original promises something the user can't deliver, change the promise, and say so.
- In their voice (`My Style/voice.md`) and spoken English (`../make-reel/references/script.md`).

Show the new script next to the breakdown, beat by beat, with a word count. Offer two alternative hooks.

## 5. Make it

When they say go (or if they asked for the whole reel at once), start the `make-reel` skill from step 1 with this script as `script.txt`. Note in the reel's `STATUS.md` which reel it remakes.
