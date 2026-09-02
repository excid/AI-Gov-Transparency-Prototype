# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js single-page prototype generated with ChatGPT Sites and shadcn components.

## Users

The primary users are procurement reviewers, auditors, and public-sector teams screening Thai TOR documents before or during procurement review. Secondary users include businesses that want to understand potentially restrictive requirements before investing time in a bid.

## Product Purpose

The product turns a TOR document into explainable warning signs that help a human decide what deserves further review. Success means a reviewer can upload a TOR, understand each warning, trace it to the source clause, and distinguish known rule violations from unusual historical patterns.

## Positioning

The product combines three distinct layers: an LLM extracts structured facts and evidence, deterministic rules identify known warning conditions, and machine learning compares the project with historical peers. It reports signals for further review, never a corruption verdict.

## Operating Context

Users work with Thai PDF procurement documents, page and clause citations, project budgets, qualification requirements, bidding timelines, historical comparable projects, and risk-screening reports.

## Capabilities and Constraints

- The prototype uses a two-step, single-route flow: PDF upload followed by evidence-linked results.
- The interface must visibly distinguish LLM extraction, rule-based checks, and ML comparison.
- Uploaded PDFs are processed by a local Python service using Thai OCR, deterministic rules, Alibaba Qwen when configured, and an unsupervised GovSpending comparison model.
- Every warning must be designed around source evidence, a transparent trigger, and a review limitation.
- Files and OCR text are not persisted; missing LLM or ML inputs produce visible degraded or abstained states.

## Evidence on Hand

The product concept and warning categories are based on the team's hackathon research and public procurement-risk patterns. No production accuracy, customer, or performance claims have been established and none should be fabricated.

## Product Principles

- Evidence before severity.
- Separate extraction, rules, and statistical inference.
- Make uncertainty visible.
- Help humans prioritize review without making allegations.
- Keep the first-use flow understandable without training.

## Accessibility & Inclusion

The interface must support keyboard navigation, visible focus, readable Thai text, responsive layouts, and color-independent severity labels.
