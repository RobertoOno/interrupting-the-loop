# Solved source world

A translation commutes with evaluation under related environments.

```lean
namespace S_sodubu
universe u v

inductive ScopedIndex : Nat → Type where
  | first {n : Nat} : ScopedIndex (Nat.succ n)
  | rest {n : Nat} : ScopedIndex n → ScopedIndex (Nat.succ n)

inductive Q_vekoji (α : Type u) : Nat → Type u where
  | q_diyewo {n : Nat} : ScopedIndex n → Q_vekoji α n
  | q_wecone {n : Nat} : α → Q_vekoji α n
  | q_xeqina {n : Nat} : Q_vekoji α n → Q_vekoji α n → Q_vekoji α n
  | q_duwoje {n : Nat} : Q_vekoji α n → Q_vekoji α (Nat.succ n) → Q_vekoji α n

def q_maqobe {α : Type u} {n : Nat} (head : α) (tail : ScopedIndex n → α) : ScopedIndex (Nat.succ n) → α
  | .first => head
  | .rest i => tail i

def q_yoguga {α : Type u} {β : Type v} (f : α → β) {n : Nat} : Q_vekoji α n → Q_vekoji β n
  | .q_diyewo i => .q_diyewo i
  | .q_wecone a => .q_wecone (f a)
  | .q_xeqina left right => .q_xeqina (q_yoguga f left) (q_yoguga f right)
  | .q_duwoje value body => .q_duwoje (q_yoguga f value) (q_yoguga f body)

def q_xerido {α : Type u} (op : α → α → α) {n : Nat}
    (env : ScopedIndex n → α) : Q_vekoji α n → α
  | .q_diyewo i => env i
  | .q_wecone a => a
  | .q_xeqina left right => op (q_xerido op env left) (q_xerido op env right)
  | .q_duwoje value body => q_xerido op (q_maqobe (q_xerido op env value) env) body

def q_novipa {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ x y, encode (opA x y) = opB (encode x) (encode y)

end S_sodubu
namespace S_sodubu
universe u v

theorem solved_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_novipa encode opA opB) {n : Nat} (t : Q_vekoji α n) :
    ∀ (envA : ScopedIndex n → α) (envB : ScopedIndex n → β),
      (∀ i, encode (envA i) = envB i) →
      encode (q_xerido opA envA t) = q_xerido opB envB (q_yoguga encode t) := by
  induction t with
  | q_diyewo i =>
      intro envA envB related
      exact related i
  | q_wecone a =>
      intro envA envB related
      rfl
  | q_xeqina left right ihLeft ihRight =>
      intro envA envB related
      simp only [q_xerido, q_yoguga]
      rw [h, ihLeft envA envB related, ihRight envA envB related]
  | q_duwoje value body ihValue ihBody =>
      intro envA envB related
      simp only [q_xerido, q_yoguga]
      apply ihBody
      intro i
      cases i with
      | first => exact ihValue envA envB related
      | rest j => exact related j

end S_sodubu

#print axioms S_sodubu.solved_bridge
```
