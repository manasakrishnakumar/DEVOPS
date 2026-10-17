# Incident reports (generated from measured data; template-based, not an LLM)

## corrupt under policy `none`
- What happened: a silent `corrupt` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 0 % correct, 100 % degraded (valid but lower quality), 0 % wrong, 0.0 % failed.
- Response: no operator.
- Outcome: Full quality was never restored; the service stayed in the degraded tier until the fault was cleared by hand.

## corrupt under policy `rules`
- What happened: a silent `corrupt` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 84 % correct, 15 % degraded (valid but lower quality), 0 % wrong, 0.9 % failed.
- Response: operator restart (history: [{"action":"restart","signature":"invalid:lstm,sarima","t":"2026-10-16T07:34:54.528773Z"},{"action":"restart","signature":"invalid:lstm,sarima","t":"2026-10-16T).
- Outcome: Full quality was restored in a median of 23.4 s (5/5 trials).

## unitchange under policy `none`
- What happened: a silent `unitchange` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 0 % correct, 100 % degraded (valid but lower quality), 0 % wrong, 0.0 % failed.
- Response: no operator.
- Outcome: Full quality was never restored; the service stayed in the degraded tier until the fault was cleared by hand.

## unitchange under policy `rules`
- What happened: a silent `unitchange` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 83 % correct, 16 % degraded (valid but lower quality), 0 % wrong, 0.4 % failed.
- Response: operator restart (history: ,sarima","t":"2026-10-16T08:44:02.315825Z"},{"action":"restart","signature":"invalid:lstm,sarima","t":"2026-10-16T08:47:06.466479Z"},{"action":"restart","signat).
- Outcome: Full quality was restored in a median of 25.6 s (5/5 trials).

## flatline under policy `none`
- What happened: a silent `flatline` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 0 % correct, 100 % degraded (valid but lower quality), 0 % wrong, 0.0 % failed.
- Response: no operator.
- Outcome: Full quality was never restored; the service stayed in the degraded tier until the fault was cleared by hand.

## flatline under policy `rules`
- What happened: a silent `flatline` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 87 % correct, 13 % degraded (valid but lower quality), 0 % wrong, 0.3 % failed.
- Response: operator restart (history: t","signature":"invalid:lstm","t":"2026-10-16T09:14:49.289952Z"},{"action":"restart","signature":"invalid:lstm","t":"2026-10-16T09:17:53.648480Z"},{"action":"re).
- Outcome: Full quality was restored in a median of 20.4 s (5/5 trials).

## scaler under policy `none`
- What happened: a silent `scaler` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 0 % correct, 0 % degraded (valid but lower quality), 0 % wrong, 0.0 % failed.
- Response: no operator.
- Outcome: Full quality was never restored; the service stayed in the degraded tier until the fault was cleared by hand.

## scaler under policy `rules`
- What happened: a silent `scaler` fault was injected into the forecasting model; the service kept answering HTTP 200.
- User impact during the 150 s window: 85 % correct, 0 % degraded (valid but lower quality), 0 % wrong, 0.3 % failed.
- Response: operator restart (history: id:lstm,sarima","t":"2026-10-16T08:59:27.902121Z"},{"action":"restart","signature":"invalid:lstm,sarima","t":"2026-10-16T09:02:32.154088Z"},{"action":"restart",).
- Outcome: Full quality was restored in a median of 24.2 s (5/5 trials).

## bitflip: guard off vs guard on
- Guard off (C4): 100 % wrong answers served, detected in 0/10 trials.
- Guard on (E4): 100 % wrong, 0 % degraded, detected in 0/10 trials.

## flatline: guard off vs guard on
- Guard off (C4): 100 % wrong answers served, detected in 0/10 trials.
- Guard on (E4): 0 % wrong, 100 % degraded, detected in 10/10 trials.

## precursor warning: leak
- Isolation Forest alarmed before the failure in 6/6 runs (median lead 69.6 s); a static memory threshold gave 6/6; the reactive guard gave 0/6.

## precursor warning: drift
- Isolation Forest alarmed before the failure in 6/6 runs (median lead 23.7 s); a static memory threshold gave 0/6; the reactive guard gave 0/6.
