# Issue Pipeline

```
Issue Input
  -> InputClassifierAgent
  -> IssueAnalystAgent
  -> RepoExplorerAgent
  -> SystemArchitectAgent
  -> TaskDecomposerAgent
  -> ImplementerAgent (via ExecutorRouter)
  -> QualityGateAgent
  -> CodeReviewerAgent
  -> VerifierAgent
  -> CommitAgent
  -> Final Report
```

Outputs land under `.dev-factory/runs/<run_id>/`. The flow fails closed on
quality-gate failure unless `--continue-and-report` is set.
