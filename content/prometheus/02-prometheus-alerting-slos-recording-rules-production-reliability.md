# Prometheus — Chunk 2 of 2: Alerting, SLOs, Recording Rules, Production Reliability & Incident Mastery

**Backend Engineering Tools & Infrastructure Handbook**

**Source file:** `content/prometheus/02-prometheus-alerting-slos-recording-rules-production-reliability.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Write actionable Prometheus alerting rules.
- Explain how Prometheus, Alertmanager, and notification channels work together.
- Design alerts around user impact rather than noisy infrastructure symptoms.
- Understand SLIs, SLOs, error budgets, and burn rates.
- Use recording rules to make expensive PromQL queries more efficient.
- Diagnose missing alerts, false positives, high-cardinality incidents, and monitoring failures.
- Explain monitoring reliability and alerting trade-offs in backend engineering interviews.

This chapter completes the three required layers of the Prometheus handbook:

1. **Fundamentals & Mental Models**
2. **Practical Engineering & Workflows**
3. **Production Engineering & Interview Mastery**

---

# Layer 1 — Fundamentals & Mental Models

## 1. The Complete Monitoring Pipeline

Prometheus collecting metrics is only the beginning. Production monitoring must turn measurements into decisions and actions.

A typical monitoring pipeline looks like this:

```text
Spring Boot Application
        |
        | Exposes /actuator/prometheus
        v
    Prometheus
        |
        | Evaluates PromQL alert expressions
        v
   Alerting Rules
        |
        | Sends firing alerts
        v
   Alertmanager
        |
        | Groups, deduplicates, routes
        v
 Email / Slack / PagerDuty / Webhook
```

Each component has a distinct responsibility.

| Component | Responsibility |
|---|---|
| Application instrumentation | Produces application metrics |
| Exporter | Exposes metrics from a system that does not natively expose Prometheus metrics |
| Prometheus | Scrapes, stores, and queries time-series metrics |
| Alerting rules | Evaluates conditions and creates alerts |
| Alertmanager | Groups, deduplicates, silences, and routes alerts |
| Notification receiver | Delivers the notification to a person or system |
| Grafana | Visualizes metrics and dashboards; can also support alerting |

**Mental model:** Prometheus detects a condition; Alertmanager manages the resulting notifications.

Prometheus does not inherently know whether a person has received or acted on an alert. Notification delivery and incident response are separate operational concerns.

## 2. What Is an Alerting Rule?

An alerting rule is a continuously evaluated expression that becomes active when its condition is true.

For example:

```promql
up == 0
```

This expression identifies targets whose most recent scrape indicates they are down.

A rule adds a name, evaluation behavior, labels, and descriptive annotations:

```yaml
groups:
  - name: backend-availability
    rules:
      - alert: BackendTargetDown
        expr: up{job="backend-api"} == 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Backend API target is down"
          description: "Prometheus has been unable to scrape this target for the alert's pending period."
```

The important fields are:

- `alert`: the alert's name.
- `expr`: the PromQL condition.
- `for`: how long the condition must remain true before the alert fires.
- `labels`: metadata used for classification and routing.
- `annotations`: human-readable context.

### Pending versus firing

Suppose the condition becomes true at 10:00 and the rule has `for: 2m`.

- At 10:00, the alert enters the pending state.
- If the condition remains true, it becomes firing after the pending period.
- If the condition clears before the period elapses, it returns to inactive.

This reduces alerts caused by brief fluctuations.

The `for` duration is not a universal solution to alert noise. If a serious failure requires immediate action, delaying it may be harmful.

## 3. What Is Alertmanager?

Prometheus evaluates rules. Alertmanager manages the alerts that are sent out.

Its core responsibilities include:

- **Grouping:** combine related alerts into one notification.
- **Deduplication:** avoid repeatedly notifying about equivalent alert states.
- **Routing:** direct alerts to appropriate receivers.
- **Inhibition:** suppress lower-priority notifications when a related higher-priority alert is firing.
- **Silencing:** temporarily suppress notifications matching specified conditions.

For example, if one database outage causes 40 API instances to fail, notifying an on-call engineer 40 separate times may create noise. Grouping can produce one notification with the relevant instance details.

Grouping should preserve useful context. Overly broad grouping can hide distinct incidents inside one notification.

## 4. Metrics Are Not the Same as Service Objectives

A metric tells you what happened. A service objective defines what level of service you intend to deliver.

Consider an API that receives 100,000 eligible requests in a measurement window.

If 99,500 requests succeed within the agreed latency threshold, the measured proportion is:

$$\text{SLI} = \frac{99{,}500}{100{,}000} = 99.5\%$$

Here is the terminology:

- **SLI — Service Level Indicator:** the measured indicator of service behavior, such as availability or latency.
- **SLO — Service Level Objective:** the target for that indicator, such as 99.9% successful requests over a rolling 30-day window.
- **SLA — Service Level Agreement:** an agreement with users or customers that may include commitments and consequences for missing them.
- **Error budget:** the amount of unreliability permitted by an SLO over its measurement window.

An SLO is not simply a dashboard threshold. It expresses an explicit reliability target.

### Error budget example

Suppose an availability SLO is 99.9% over a 30-day window.

The allowed failure proportion is:

$$1 - 0.999 = 0.001 = 0.1\%$$

Using a 30-day window of 43,200 minutes, a time-based approximation of the budget is:

$$43{,}200 \times 0.001 = 43.2\text{ minutes}$$

This time-based calculation is only an approximation when the SLI is request-based. If requests vary significantly over time, calculate the budget using eligible request counts instead.

The error budget creates a practical trade-off: when reliability is within budget, the team may have room for more change; when the budget is being consumed rapidly, the team may need to prioritize reliability work.

## 5. Alert on Symptoms and Causes

A useful monitoring system distinguishes user-visible symptoms from infrastructure causes.

**Symptom-oriented alerts** include:

- The API's successful-request ratio is falling.
- Request latency is exceeding the service objective.
- The error budget is being consumed too quickly.

**Cause-oriented alerts** include:

- CPU utilization is unusually high.
- A disk is approaching capacity.
- Kafka consumer lag is increasing.
- A database connection pool is nearly exhausted.

Both categories matter, but they serve different purposes. Symptom alerts help establish user impact; cause alerts help diagnose it.

A CPU alert by itself does not prove the service is unhealthy. High CPU can be expected during normal load. Conversely, an API may be returning errors while CPU remains low.

**Production principle:** Prioritize alerts that indicate a real problem requiring action. Use infrastructure alerts as supporting diagnostic signals.

---

# Layer 2 — Practical Engineering & Workflows

## 6. Build a Reproducible Local Monitoring Lab

This lab assumes that you already have a Prometheus configuration and Spring Boot metrics endpoint from Chunk 1. Use the following as an extension, adapting paths and service names to your existing Compose project.

Recommended structure:

```text
monitoring/
├── prometheus.yml
├── alert-rules.yml
└── alertmanager.yml
```

### Step 1 — Configure rule evaluation

Add a rule-file reference and an evaluation interval to `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alert-rules.yml

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["prometheus:9090"]

  - job_name: backend-api
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["backend-api:8080"]
```

The target names must be resolvable from the Prometheus container's network. In Docker Compose, a service name usually works when the services share a network.

### Step 2 — Create actionable alert rules

Create `alert-rules.yml`:

```yaml
groups:
  - name: backend-availability
    rules:
      - alert: BackendTargetDown
        expr: up{job="backend-api"} == 0
        for: 2m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "Backend API is unreachable by Prometheus"
          description: "Inspect target health, application logs, networking, and recent deployments."

  - name: backend-performance
    rules:
      - alert: BackendHigh5xxRate
        expr: |
          (
            sum(rate(http_server_requests_seconds_count{
              job="backend-api",
              status=~"5.."
            }[5m]))
            /
            clamp_min(
              sum(rate(http_server_requests_seconds_count{
                job="backend-api"
              }[5m])),
              0.001
            )
          ) > 0.05
        for: 5m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "Backend server-error ratio is elevated"
          description: "More than 5% of observed requests are returning 5xx responses."
```

**Important:** The metric name and labels depend on your Spring Boot and Micrometer configuration. Verify the actual series at `/actuator/prometheus` before using these rules. A rule that references nonexistent metrics will not deliver the intended alert.

The 5% threshold is illustrative, not a recommended universal production threshold. Real thresholds should reflect the service's SLO, traffic volume, and acceptable error rate.

The denominator uses `clamp_min` to avoid division by zero, but that does not make a low-traffic ratio statistically reliable. Production rules should also account for minimum traffic volume and the service's actual reliability objective.

### Step 3 — Validate the rules

Use Prometheus's rule validation tooling where available, and then inspect the running instance.

Useful checks:

```bash
promtool check rules monitoring/alert-rules.yml
```

After reloading or restarting Prometheus, inspect:

- The **Rules** page to confirm that the rules loaded.
- The **Alerts** page to see inactive, pending, and firing states.
- The **Targets** page to confirm that the backend is being scraped.
- The query interface to verify each expression independently.

A syntactically valid rule can still be logically incorrect. Always test its PromQL expression against real series.

## 7. Configure Alertmanager

Create `alertmanager.yml`:

```yaml
route:
  receiver: default-receiver
  group_by: ["alertname", "team", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: default-receiver
```

This defines routing and grouping, but it does not deliver a notification to an external service because no delivery integration has been configured.

For real notifications, add a supported receiver such as an email integration, webhook, or incident-management service. Store credentials securely and avoid committing them to Git.

A minimal Compose extension could include:

```yaml
services:
  alertmanager:
    image: prom/alertmanager:latest
    command:
      - "--config.file=/etc/alertmanager/alertmanager.yml"
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "9093:9093"
```

This assumes the configuration file exists and that the service joins the relevant Compose network. Production deployments should pin image versions rather than relying on `latest`, and should use deliberate network and port exposure policies.

If Prometheus is running in a container, configure its alerting section to reach Alertmanager by the Compose service name:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]
```

The `alerting` section belongs in `prometheus.yml`, at the top level. Ensure the Alertmanager service is reachable from Prometheus.

### Alert lifecycle walkthrough

1. A backend metric changes.
2. Prometheus scrapes the metric.
3. The alert expression evaluates to true.
4. The alert waits through its configured `for` period, if any.
5. Prometheus sends the firing alert to Alertmanager.
6. Alertmanager groups and routes it.
7. A configured receiver delivers the notification.

Test this complete chain. Seeing an alert marked as firing in Prometheus does not prove the notification reached the on-call engineer.

## 8. Recording Rules: Precompute Expensive Queries

A recording rule periodically evaluates a PromQL expression and stores the result as a new time series.

Why is this useful?

A dashboard may repeatedly calculate the same expensive aggregation across many application instances. Instead of running that full expression for every dashboard refresh, Prometheus can calculate it on a schedule.

Example:

```yaml
groups:
  - name: backend-recording-rules
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: |
          sum by (job) (
            rate(http_server_requests_seconds_count[5m])
          )
```

You can then query the recorded result:

```promql
job:http_requests:rate5m
```

Recording rules are useful for:

- Frequently used dashboard queries.
- Repeated aggregations across many instances.
- Standardized service-level metrics.
- Reducing the cost of complex queries.

However, recording rules consume storage and evaluation resources. They also introduce a refresh interval, so the recorded result is not necessarily identical to evaluating the original expression at the current instant.

### Naming conventions

A common style is:

```text
level:metric:operations
```

For example:

```text
job:http_requests:rate5m
```

The name should communicate the aggregation level, metric, and operation. Consistency is more important than mechanically following a convention without understanding it.

### When not to use recording rules

Avoid creating recording rules for every query. Prefer them when a query is frequently reused or expensive enough to justify precomputation.

Before adding one:

1. Measure the query's cost.
2. Check whether the result is reused.
3. Choose a suitable evaluation interval.
4. Confirm the new series has controlled cardinality.
5. Verify that dashboards and alerts use the recorded series correctly.

## 9. Design Useful SLIs and SLOs

Consider a Spring Boot Orders API.

Possible SLIs include:

- Availability: proportion of eligible requests that succeed.
- Latency: proportion of eligible requests completed within a defined threshold.
- Correctness: proportion of operations that produce valid outcomes, if correctness can be measured reliably.

For a request-based availability SLI:

```promql
sum(rate(http_server_requests_seconds_count{
  job="backend-api",
  status!~"5.."
}[5m]))
/
sum(rate(http_server_requests_seconds_count{
  job="backend-api"
}[5m]))
```

This is only a basic example. The definition of success must match the service contract: not every non-5xx response necessarily means a request was successful from the user's perspective. Exclusions such as health checks and expected client errors should be defined deliberately.

For a latency objective using a histogram, suppose the target is that 95% of requests complete within 300 ms:

```promql
sum(rate(http_server_requests_seconds_bucket{
  job="backend-api",
  le="0.3"
}[5m]))
/
sum(rate(http_server_requests_seconds_count{
  job="backend-api"
}[5m]))
```

This computes the observed fraction of requests in the histogram bucket at or below 0.3 seconds, assuming the histogram's buckets and count series are configured consistently.

It is often more useful to measure the fraction of requests that meet the latency objective than to alert on a percentile alone.

**Why?** A percentile can obscure the number of users affected, particularly at low traffic volumes. A good SLI definition makes the user impact explicit.

## 10. Error Budgets and Burn Rates

An error budget describes how much unreliability is allowed by the SLO. A burn rate measures how quickly that budget is being consumed relative to the target.

For an availability SLO of 99.9%, the allowed error ratio is:

$$1 - 0.999 = 0.001$$

If the observed error ratio is 0.01, then:

$$\text{Burn rate} = \frac{0.01}{0.001} = 10$$

The service is consuming its error budget at ten times the sustainable rate during that measurement window.

A high burn rate can justify paging even when the raw error percentage looks modest. Conversely, a small absolute number of errors at low traffic may not justify an immediate page.

Production alerting commonly evaluates different windows:

- A short window catches sudden incidents.
- A longer window reduces sensitivity to brief spikes.
- Combining windows can distinguish sustained degradation from transient noise.

Exact windows and thresholds depend on the SLO, traffic, and response expectations. Do not copy generic burn-rate thresholds without validating them against your service.

## 11. Debugging Prometheus Rules and Alerts

Use this checklist when an expected alert does not fire.

### A. Confirm the target is being scraped

```promql
up{job="backend-api"}
```

If the series is absent, investigate target discovery and scrape configuration. If it exists with value `0`, inspect connectivity, endpoint paths, authentication, and application availability.

### B. Confirm the metric exists

```promql
{job="backend-api"}
```

Use the query browser and metrics endpoint to discover actual names and labels. Avoid assuming a metric exists because an example online uses it.

### C. Run the alert expression manually

Evaluate the exact `expr` in the Prometheus query interface. Check whether it returns the series and values you expect.

### D. Inspect rule state

Confirm the rule loaded and determine whether it is inactive, pending, or firing. A `for` duration may explain why a true condition has not yet fired.

### E. Inspect Alertmanager

If Prometheus shows a firing alert but no notification arrives, verify:

- Prometheus can reach Alertmanager.
- Alertmanager has loaded its configuration.
- The alert matches a route.
- A receiver is configured correctly.
- Delivery credentials and external service settings are valid.
- The alert is not silenced or inhibited.

### F. Check time and labels

Unexpected timestamps, inconsistent labels, aggregation mistakes, or an overly restrictive matcher can cause alerts to disappear from a query or route.

---

# Layer 3 — Production Engineering & Interview Mastery

## 12. Production Alerting Principles

### Principle 1: Every page needs an action

A page should make it reasonably clear what the responder should investigate or do.

Weak annotation:

```yaml
summary: "High CPU"
```

Better annotation:

```yaml
summary: "Orders API CPU saturation is affecting request latency"
description: "Check request latency, recent deployments, CPU throttling, and thread-pool saturation for the Orders API."
```

The second annotation offers context and initial diagnostic direction. It does not claim that CPU is necessarily the root cause.

### Principle 2: Separate pages from tickets

A page is for urgent, actionable conditions requiring timely human response. Lower-priority conditions can be routed to a ticket, dashboard, or periodic review.

Paging every time a noncritical threshold is crossed creates alert fatigue. Excessive alert volume makes genuinely urgent incidents easier to miss.

### Principle 3: Avoid one-size-fits-all thresholds

A CPU threshold suitable for one service may be irrelevant to another. Consider:

- Baseline and expected workload.
- User-visible latency and error rates.
- Traffic volume.
- Recovery time.
- SLOs and business impact.
- The cost of a missed alert versus a false alarm.

### Principle 4: Monitor the monitoring system

Prometheus can fail, become overloaded, lose connectivity, or stop evaluating rules correctly.

Monitor the monitoring pipeline itself:

- Prometheus target health.
- Rule evaluation failures and duration.
- Storage capacity and retention.
- Prometheus process health.
- Alertmanager health and notification failures.
- Gaps in expected metric ingestion.

An alerting system that silently stops working can create a false sense of safety.

## 13. Cardinality and Scaling Risks

Prometheus creates a distinct time series for each unique combination of metric name and label values.

Consider:

```text
http_requests_total{method="GET",status="200",instance="api-1"}
```

Adding a label such as `user_id` can produce a large number of unique combinations. The problem becomes worse when multiple high-cardinality labels are combined.

Avoid labels containing unbounded or highly variable values, such as:

- User IDs.
- Request IDs.
- Raw URLs containing unique identifiers.
- Email addresses.
- Arbitrary error messages.

Prefer bounded labels such as HTTP method, normalized route, status class, and service name.

Use logs or traces for high-cardinality diagnostic details. Metrics should efficiently answer aggregate operational questions.

### Production safeguards

- Establish a metric and label naming standard.
- Review instrumentation before release.
- Watch active-series growth.
- Set appropriate retention and storage capacity.
- Avoid scraping unnecessarily expensive endpoints.
- Use recording rules for justified recurring aggregations.
- Keep labels stable across deployments where possible.
- Evaluate the cost of every new metric family.

Do not treat dropping metrics indiscriminately as the first response to storage pressure. Identify the cardinality source and preserve the measurements required for service reliability.

## 14. Security and Reliability

Prometheus metrics can expose internal architecture, endpoint names, workload behavior, and operational details. Monitoring endpoints should not automatically be public.

Production safeguards include:

- Restricting access to Prometheus and Alertmanager interfaces.
- Exposing only necessary application endpoints.
- Using network policies, firewalls, and authentication where appropriate.
- Keeping receiver credentials outside source control.
- Using TLS where required by the deployment environment.
- Controlling who can create silences or change routing.
- Testing configuration changes before applying them.
- Keeping versions and upgrades under change control.
- Planning storage, retention, and recovery procedures.

Prometheus's pull architecture is operationally convenient, but it is not a complete security boundary. Network reachability and endpoint permissions still matter.

### Configuration and deployment discipline

For monitoring configuration changes:

1. Review the diff.
2. Validate syntax and rules.
3. Test important expressions.
4. Confirm target labels and routing behavior.
5. Deploy through a controlled workflow.
6. Verify the new configuration is loaded.
7. Confirm expected alerts still fire and clear correctly.

A monitoring change can be a production change. A typo in an alert expression may silently remove coverage for an important failure.

## 15. Production Incident Simulations

### Incident A — API is down, but there is no page

**Symptoms:** The API is unavailable, but the on-call engineer receives no notification.

**Investigation:**

1. Check whether Prometheus itself is healthy.
2. Inspect `up{job="backend-api"}`.
3. Confirm the target is present in the scrape configuration.
4. Check whether the alert rule loaded.
5. Evaluate the rule expression manually.
6. Inspect pending and firing state.
7. Check Prometheus-to-Alertmanager connectivity.
8. Inspect routing, silences, and receiver configuration.

**Likely causes:** Missing target discovery, incorrect job labels, a bad expression, a failed rule load, or a notification-routing problem.

**Engineering lesson:** A healthy dashboard is not proof that the alerting path is healthy.

### Incident B — Every deployment causes hundreds of alerts

**Symptoms:** A routine rollout produces a burst of notifications.

**Investigation:**

1. Group alerts by alert name, service, and team.
2. Check whether many instance-level alerts share one underlying cause.
3. Inspect deployment and scrape timing.
4. Determine whether the alert threshold is too sensitive to short-lived transitions.
5. Review whether a `for` duration is appropriate.
6. Configure grouping and inhibition carefully.
7. Ensure a genuine prolonged outage still generates an actionable notification.

**Likely fixes:** Better grouping, more meaningful alert scope, an appropriate pending duration, and improved rollout-aware monitoring.

**Caution:** Do not suppress all alerts during deployment. A rollout can create a real outage that needs intervention.

### Incident C — Prometheus storage grows unexpectedly

**Symptoms:** Disk usage rises rapidly and Prometheus begins experiencing storage pressure.

**Investigation:**

1. Inspect disk capacity and Prometheus logs.
2. Review active-series growth and ingestion volume.
3. Identify recently introduced metrics and labels.
4. Check for unbounded values in labels.
5. Review scrape frequency and target count.
6. Examine retention and storage configuration.
7. Estimate the effect of corrective changes before deployment.

**Likely fix:** Remove or redesign unnecessary high-cardinality instrumentation, then tune retention and storage capacity according to the monitoring requirements.

**Engineering lesson:** Metrics design is a resource-management decision, not merely an instrumentation decision.

### Incident D — The dashboard is green, but users report slow requests

**Symptoms:** A service dashboard appears healthy, yet customers report elevated latency.

**Investigation:**

1. Confirm the dashboard covers the affected route and user traffic.
2. Inspect request-duration histograms and traffic distribution.
3. Compare recent deployments and dependency latency.
4. Check whether the dashboard uses averages that hide tail latency.
5. Verify that the instrumentation is present and current.
6. Examine database, Redis, and downstream-service metrics.
7. Compare observed behavior with the defined latency SLO.

**Likely causes:** Incomplete instrumentation, overly broad aggregation, a dashboard that hides tail latency, or a slow dependency.

**Engineering lesson:** A dashboard is a view of selected measurements, not proof of service health.

## 16. Prometheus Interview Questions and Answers

### Fundamentals

**1. What is Prometheus?**

Prometheus is a monitoring and time-series database system that collects metrics, stores time-stamped samples, supports PromQL queries, and evaluates alerting and recording rules.

**2. How does Prometheus collect metrics?**

Typically, it scrapes HTTP endpoints exposed by applications or exporters at configured intervals.

**3. What is a time series?**

A named metric identified by its label set, with timestamped sample values.

**4. What is cardinality?**

The number of distinct time series. Cardinality can grow rapidly when metrics have many label combinations.

**5. What is PromQL?**

Prometheus's query language for selecting, aggregating, and calculating over time-series data.

### Alerting

**6. What is the difference between Prometheus and Alertmanager?**

Prometheus collects and queries metrics and evaluates rules. Alertmanager groups, deduplicates, inhibits, silences, and routes alerts to notification receivers.

**7. What does `for: 5m` mean in an alert rule?**

The condition must remain true for five minutes before the alert becomes firing.

**8. What is the difference between an alerting rule and a recording rule?**

An alerting rule creates an alert when an expression meets a condition. A recording rule evaluates an expression periodically and stores the result as a new time series.

**9. What is alert fatigue?**

A situation where excessive or noisy notifications reduce the likelihood that responders notice and act on important alerts.

**10. How do you debug an alert that does not fire?**

Check target health, metric existence, the expression, rule loading, pending duration, labels, and Alertmanager routing.

### Reliability and SLOs

**11. What is an SLI?**

A quantitative indicator of service behavior, such as successful-request ratio or the proportion of requests meeting a latency threshold.

**12. What is an SLO?**

A target for an SLI over a defined measurement window.

**13. What is an error budget?**

The permitted unreliability implied by an SLO over its measurement window.

**14. What is a burn rate?**

The rate at which a service consumes its error budget relative to the sustainable rate defined by the SLO.

**15. Why can a 5xx-rate alert be misleading at low traffic?**

A small number of failures can create a high ratio, while the ratio may also be based on too few observations to be stable. Traffic volume and user impact should inform the alert design.

### Production Engineering

**16. Why should user IDs generally not be Prometheus labels?**

They can create an enormous number of unique time series, increasing memory, storage, and query costs.

**17. What are recording rules used for?**

They precompute and store frequently reused or expensive expressions, making dashboards and alerts more efficient.

**18. Why should you monitor Prometheus itself?**

Because collection, rule evaluation, storage, or notification delivery can fail, leaving the team without reliable visibility.

**19. How would you investigate a sudden increase in Prometheus disk usage?**

Inspect ingestion and active-series growth, review recent metric and label changes, identify high-cardinality series, and check retention and storage settings.

**20. Why is a symptom-oriented alert often more useful than a CPU alert?**

A symptom such as a rising request-error ratio directly indicates user-visible degradation. CPU utilization is a diagnostic signal whose significance depends on workload and service behavior.

## 17. Hands-On Capstone

Build a monitoring and alerting workflow for a Spring Boot Orders API.

### Required tasks

- [ ] Expose application metrics through Micrometer and Spring Boot Actuator.
- [ ] Configure Prometheus scraping.
- [ ] Verify the target is healthy.
- [ ] Write an alert for an unavailable backend target.
- [ ] Write a service-error-ratio alert using the actual metrics available.
- [ ] Configure Alertmanager with at least one real or local test receiver.
- [ ] Confirm that a firing alert reaches the receiver.
- [ ] Create a recording rule for a frequently used aggregation.
- [ ] Define one availability SLI and one latency SLI.
- [ ] Specify an SLO and explain its error budget.
- [ ] Simulate a missing metric or unreachable target.
- [ ] Diagnose a notification that fails to arrive.
- [ ] Review metric labels for cardinality risks.
- [ ] Document the incident, evidence, root cause, and preventive action.

### Completion standard

You should be able to explain the entire path from a backend metric to a human notification, distinguish a real service-level objective from a dashboard threshold, and troubleshoot a failure without relying on guesswork.

---

# Final Mastery Checklist

Before marking Prometheus complete, verify that you can:

- [ ] Explain Prometheus's pull-based collection model.
- [ ] Distinguish counters, gauges, histograms, and summaries.
- [ ] Write and validate PromQL expressions.
- [ ] Explain alerting-rule states and the `for` duration.
- [ ] Describe the division of responsibility between Prometheus and Alertmanager.
- [ ] Configure grouping, routing, and notification delivery.
- [ ] Explain SLIs, SLOs, SLAs, and error budgets.
- [ ] Explain recording rules and when to use them.
- [ ] Diagnose missing targets, metrics, rules, and notifications.
- [ ] Recognize high-cardinality instrumentation.
- [ ] Design actionable alerts with clear responder guidance.
- [ ] Explain how to monitor the monitoring system.
- [ ] Complete the capstone and defend the design trade-offs.

## Prometheus Handbook Completion Protocol

This is the second and final planned Prometheus content chunk. The Prometheus curriculum is now **complete in authored content**.

Repository and release work remain separate:

1. Save this chapter as `content/prometheus/02-prometheus-alerting-slos-recording-rules-production-reliability.md`.
2. Verify that Chunk 1 and Chunk 2 both exist in `content/prometheus/` and contain the complete source content.
3. Review the combined handbook for consistency, working examples, and accurate metric names.
4. Generate the **single complete Prometheus PDF**, not separate PDFs per chunk, at `docs/prometheus/BEH_PROMETHEUS_COMPLETE_HANDBOOK.pdf`.
5. Open and verify the PDF, including its examples, formatting, and completeness.
6. Update the README using verified progress only.
7. After the source files and final PDF are saved and verified, commit with the exact message:

`Prometheus done`

**Do not mark the repository, PDF, or Git commit complete until those steps have actually been executed and verified.**
