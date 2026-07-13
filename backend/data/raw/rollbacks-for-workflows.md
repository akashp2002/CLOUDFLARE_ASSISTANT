---
title: How we built saga rollbacks for Cloudflare Workflows
url: https://blog.cloudflare.com/rollbacks-for-workflows/
date: 2026-06-25
---

Cloudflare Workflows allows you to build durable, multi-step applications with built-in retries and state persistence across long-running processes. When a __Workflow__ executes, each step can call external systems, retry failures, and persist state across restarts. But if one step fails, it may leave earlier work from completed steps in an inconsistent or partial state.

Today we’re shipping saga rollbacks for Workflows, allowing you to declare rollback logic within the step itself, in case of failure.

For example, consider a workflow for transferring funds between accounts at two different banks:

- Debit from account at Bank A 
- Credit to account at Bank B 
- Send email confirmation to both account owners 

What happens if Step 2, the credit to account at Bank B, fails? Once the debit succeeds at Bank A, the transaction is committed and the money has left its system. As the orchestrator of the transaction, you cannot simply “undo” the operation in Bank A's system. Instead, the money must be credited back to the account at Bank A through a new operation that semantically reverses the first one.

          
This pairing of an operation and its compensation logic is called the __saga pattern__.

Before today, developers had to implement their own compensation logic to track what succeeded, what failed, and what actions should be taken upon failure, outside of the steps’ direct definitions. Now, you can define compensation logic for each `step.do()` as an argument within the steps themselves, maintaining your workflow’s durability for the rollback as well.

            ```
// track what completed so we know what to undo
let debitA;
let creditB;
try {
  debitA = await step.do("debit-bank-a", () => bankA.debit(from, amount));
  creditB = await step.do("credit-bank-b", () => bankB.credit(to, amount));
  await step.do("notify", () => notifyBoth(from, to, amount));
} catch (error) {
  // unwind in reverse. each undo is its own durable step,
  // must be idempotent, and must keep going if one fails.
  if (creditB) {
    try {
      await step.do("reverse-credit-b", () => bankB.debit(to, amount, creditB.id));
    } catch (e) {
      await alertOnCall("reverse-credit-b failed", e);
    }
  }
  if (debitA) {
    try {
      await step.do("refund-debit-a", () => bankA.credit(from, amount, debitA.id));
    } catch (e) {
      await alertOnCall("refund-debit-a failed", e);
    }
  }
  throw error;
}
```

            Without rollbacks

            ```
// each step ships with its own undo. add a step,
// add its rollback right here. no growing catch
// block, no manual ordering, no replay logic.
await step.do("debit-bank-a", () => bankA.debit(from, amount), {
  rollback: async ({ output }) => bankA.credit(from, amount, output.id),
});
await step.do("credit-bank-b", () => bankB.credit(to, amount), {
  rollback: async ({ output }) => bankB.debit(to, amount, output.id),
});
await step.do("notify", () => notifyBoth(from, to, amount));
```

            With rollbacks

    
    To use rollbacks, just pass an options object containing a `rollback` function as the last argument to `step.do()`.

            ```
const debit = await step.do(
  "debit-account-a",
  async () => {
    return await bankA.debit({
      accountId: fromAccountId,
      amount,
      idempotencyKey: `${transferId}:debit-account-a`,
    });
  },
  {
    rollback: async () => {
      await bankA.credit({
        accountId: fromAccountId,
        amount,
        idempotencyKey: `${transferId}:rollback-debit-account-a`,
      });
    },
  }
);
// The idempotency keys make both the forward operations and rollback operations safe to retry without duplicating the transfer
const credit = await step.do(
  "credit-account-b",
  async () => {
    return await bankB.credit({
      accountId: toAccountId,
      amount,
      idempotencyKey: `${transferId}:credit-account-b`,
    });
  },
  {
    rollback: async ({ output }) => {
      if (output === undefined) {
        return;
      }
      await bankB.debit({
        accountId: toAccountId,
        amount,
        idempotencyKey: `${transferId}:rollback-credit-account-b`,
      });
    },
  }
);
// If we fail here, we may want to revert all previous payments. Users should not have to wrap their code in complex try-catch logic just to revert two small payments (see below)
await step.do("send-confirmation", async () => {
  await sendTransferConfirmation({ ... });
});
```

            Rollback functions should be idempotent, just like regular Workflow steps. If you refund a charge, use the payment provider's idempotency key. If you release inventory, make the release safe to call more than once.

If any step fails, the rollback handlers will execute in reverse `step-start` order. It sounds simple: run the undo steps when something fails. In practice, there are a few details that make the API and execution model important.

1. **The failed step may still need rollback. **A failed `step.do()` can still be rollback-eligible if it registered a rollback handler.

The rollback will not start if user code catches an error and the Workflow continues, but if a step error is caught and the Workflow later fails for another reason, rollback can still run for previously registered handlers, which execute in reverse `step-start` order.

Why? The step may have partially interacted with an external system before failing. For example, a payment provider may capture a charge, but the step may fail before returning the `chargeId` to Workflows. That is why rollback handlers receive `output`, but must handle `output === undefined`.

2. **Rollback only starts when the Workflow fails. **Adding a rollback handler does not mean every step error triggers rollback. If user code catches an error and continues, the Workflow continues. Rollback starts when the Workflow itself is about to fail terminally.

When rollback starts, Workflows finds eligible `step.do()` calls, runs their rollback handlers, then records the final Workflow failure.

3. **Ordering has to be predictable. **For sequential Workflows, rollback order feels obvious:

- Reserve inventory. 
- Charge card. 
- Create shipment. 
- If shipment fails, refund the card and release the inventory. 

Parallel steps make this more subtle. Completion order can differ from start order, so Workflows uses reverse step-start order instead of reverse completion order.

The practical rules are:

- Any started or completed steps with rollback handlers are eligible. 
- The failing - `step.do()`is also eligible if it registered a rollback handler.
 
- Handlers run in reverse step-start order, not completion order. 

Once we had the expected behavior in mind, we had to add this new pattern into the Workflows API. Rollbacks went through a few iterations before we landed on `rollback options`. 

    
### Why not a fluent or builder API?

      
        
      
     
    The first approach was a fluent form: `step.do(...).rollback(...)` It reads well. The forward action and the compensation sit next to each other, and the call site looks like ordinary JavaScript chaining.

The problem is that `step.do()` already has an important meaning: it starts a durable step and returns a Promise for the step output. In Workers, promise-like values are especially meaningful because Workers RPC supports __promise pipelining__, a pattern inherited from systems like __Cap'n Proto__.

Promise pipelining lets code call a method on a future value before that value has fully returned to the caller. For example:

            ```
const session = api.authenticate(apiKey);
const name = await session.whoami();
```

            Here, `session` is not the real session object yet. It is more like a handle to the session that will exist soon. When you call `session.whoami()`, Workers can send that call to the remote side early and say: “once authentication creates the session, call `whoami()` on it.”

          That saves a round trip. The caller does not need to wait for `authenticate()` to fully finish before asking for `whoami()`.

We considered a fluent API:

            `step.do("charge-card", chargeCard).rollback(refundCharge);`

            
To a reader, that can look like “call `.rollback()` on the result of `charge-card`.”   But rollback is not part of the step’s output. It is part of the `step.do()` options, registered before the step starts, so Workflows knows how to compensate the step if a later step fails.

A fluent API also makes step timing harder to reason about. Today, `step.do()` starts the step when it is called, so developers can start a step, do other work, and await the first step later:

            ```
const first = step.do("first", () => serviceA.call());
await step.do("second", () => serviceB.call());
await first;
```

            With today’s execution model, `first` starts immediately, before `second`. A fluent API would complicate that. Workflows would need to wait and see whether `.rollback()` gets attached before it knows the full step definition. That could delay when the step is sent to the engine.

In the earlier example, `first` could start at `await first` instead of at `step.do("first", ...)`, after `second` has already completed.

That makes concurrent Workflows harder to reason about: step timing would depend on when the returned `Promise` is consumed, not just where `step.do()` is called.

We also considered a builder-style API:

            ```
const charge = await step
	.saga("charge")
	.do(() => chargeCard())
	.rollback(() => refundCharge())
	.run();
```

            A builder API avoids the `Promise` ambiguity. It also gives us an obvious place for future step-level options, and makes it clear that the forward action and rollback action belong to the same saga step.

But it adds ceremony. Every step needs a final `.run()`, forgetting `.run()` would be easy and hard to spot without tooling, and simple one-step cases start to look like configuration chains. It also introduces a new `step.saga()` builder, breaking from the existing `step.<action>` pattern. Most importantly, it makes `step.do()` feel like an older API rather than the primary Workflows primitive. The goal of rollback was to extend `step.do()`, not replace it.

    
    
            `step.do(..., { rollback })`

            Ultimately, we chose the explicit form where rollback is metadata on the step.

This way, each rollback is defined within the forward step itself. Each handler receives the error that caused the rollback to start, the __step context__, and the output, which is either the persisted value returned by the forward step (which can be undefined) or undefined if the step failed before persisting a value.

Rollbacks emit lifecycle events, so you can tell whether compensation started, which rollback handler failed, and whether rollback completed successfully.

Crucially, the original Workflow failure remains separate: rollback is what Workflows does after the failure, not the reason the Workflow failed.

Just as you can define custom retry and timeout behavior in the __step configuration__ via `WorkflowStepConfig`, you add rollback-specific values in `rollbackConfig`.

            ```
{
  rollback: async ({ output }) => {
    await bankA.credit({ accountId: fromAccountId, amount, transferId: `${transferId}-reversal` });
  },
  rollbackConfig: {
    retries: { limit: 10, delay: '30 seconds', backoff: 'exponential' },
    timeout: '2 minutes',
  },
}
```

            This matches the lifecycle-event mental model we wanted. A `step.do()` already describes a durable unit of work that Workflows records, retries, and later shows in logs. Rollback is another lifecycle behavior for that same unit of work. It should travel with the step definition, not live in a separate wrapper or builder.

- The step still starts when - `step.do()`normally starts.
 
- The returned promise still represents the step output. 
- Concurrent Workflow code keeps the same execution model. 
- Retry and timeout options for rollback live next to the rollback handler. 
- Existing - `step.do()`calls keep working exactly as they do today.
 

This shape is slightly more explicit than the fluent API, but that explicitness is useful. The operation and its compensation are still in one place, and the API does not introduce a new step builder or a new kind of promise. Developers who already understand `step.do()` only need to learn one additional `options` object.

This is less magical, but it is simpler to adopt, and clearer to understand.

    
## How it works under the hood

      
        
      
     
    Rollback feels like a small API addition, but it changes what Workflows needs to record about each step.

A regular `step.do()` already has a durable record. Workflows records that the step started, whether it completed, what it returned, and whether it should be skipped instead of repeated if the Workflow resumes later.

Rollbacks add one more thing to that record: whether the step registered compensation logic.

This means Workflows has two pieces of information to bring together if the Workflow fails.

The first is **durable step history**. The Workflow engine stores data to know what ran, what completed, what output was saved, and whether rollback was registered.

The second is the **rollback handler** itself, which is the function written to compensate for that step. Workflows does not save the text of that function as data. Instead, it keeps a callable reference to the handler while the Workflow is running.

In Workers RPC, this kind of callable reference is called a __stub____dup()__

For rollback, that model is useful. The durable step history records what needs compensation. The rollback stub gives Workflows a way to invoke the compensation code. And because rollback handlers may need to outlive the immediate `step.do()` call that registered them, Workflows keeps its own callable reference to the handler for the rollback phase.

In the common case, when a Workflow enters rollback in the same engine lifetime, Workflows already has the rollback stubs it needs. It can use the durable step history to find eligible steps, then invoke the rollback stubs that were registered during forward execution.

This gets more subtle when Workflows has to **recover** after a restart.

If the engine is evicted, crashes, or restarts while rollback is needed, Workflows still has the durable step history, but it may no longer have the in-memory rollback stubs. To recover, Workflows uses **replay**: a recovery mode where it can re-run the Workflow code without re-executing completed forward step bodies.

When replay reaches a completed `step.do()`, Workflows reads the persisted result instead of running the step body again. For rollback recovery, Workflows only needs to rebuild handlers for steps that had rollback attached and are eligible for rollback. As those `step.do() `calls are encountered, their rollback options can register the callable stubs again

That lets Workflows recover the rollback handlers it needs without duplicating the original external side effects.

          With those pieces in place, rollback can work whether the handler is still available in memory or has to be rebuilt during recovery.

When the workflow is about to fail, Workflows does not ask your application to reconstruct what happened. It already has the step history. It can look at the persisted record and answer the important questions:

- Which steps started? 
- Which steps finished? 
- Which failed step may still need cleanup? 
- Which steps registered rollback handlers? 
- What output should each rollback handler receive? 
- What order should compensation run in? 

Then Workflows invokes each rollback stub with a rollback context: the original error, the step context, and the step output, if one was persisted.

The ordering detail matters. In normal JavaScript, especially with `Promise.all()`, completion order is not always the same as start order. If step A starts first and step B starts second, step B might finish first. For rollback, Workflows uses the persisted start order as the stable source of truth, then unwinds it in reverse.

Rollback handlers also run through Workflows' normal step machinery. That means compensation gets the same operational properties you expect from Workflows: retries, timeouts, lifecycle events, logs, and a final recorded outcome. If a rollback handler keeps failing after its configured retries, Workflows records the rollback outcome as failed, stops running the remaining rollback handlers, and the Workflow instance ultimately ends in the `Errored` state.

This is the main difference between saga rollbacks and a `catch` block. A `catch` block only knows what is still in memory at its exact point in your JavaScript execution. Workflows rollback uses persisted step history to decide what already happened, invokes the stubs it already has in the common case, and safely rebuilds missing stubs during recovery when it needs to.

That is also why the API puts rollback on `step.do()` itself. Rollback is not a separate global error handler — it is metadata attached to the durable unit of work Workflows already understands.

    
    Our first iteration of rollbacks includes: 

- Explicit per-step rollback handlers for - `step.do()`
 
- Sequential rollback execution 
- Retry and timeout configuration for compensation 

Next, we want to explore:

When a multi-step application fails halfway through, the hardest part is often not knowing *that* it failed. It is knowing *what* already happened, and what needs to happen next.

Saga rollbacks let you put that answer directly beside each step. If you are building multi-step applications with Workflows, try saga rollbacks and tell us what compensation patterns you want next. Get started with the __Workflows documentation__ and share feedback in the __Cloudflare Community__.