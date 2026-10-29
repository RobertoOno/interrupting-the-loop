# Solved source world

This independent world proves that evaluation commutes with a mirrored translation.

```lean
namespace S_tidolu

universe u v

inductive Q_yabizo (α : Type u) where
  | q_fevuca : α → Q_yabizo α
  | q_jiretu : Q_yabizo α → Q_yabizo α → Q_yabizo α

def q_kayomo {α : Type u} {β : Type v} (f : α → β) : Q_yabizo α → Q_yabizo β
  | .q_fevuca x => .q_fevuca (f x)
  | .q_jiretu left right => .q_jiretu (q_kayomo f right) (q_kayomo f left)

def q_cuyaxe {α : Type u} (op : α → α → α) : Q_yabizo α → α
  | .q_fevuca x => x
  | .q_jiretu left right => op (q_cuyaxe op left) (q_cuyaxe op right)

def q_fulidu {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ (x y : α), encode (opA x y) = opB (encode y) (encode x)

theorem solved_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_fulidu encode opA opB) :
    ∀ t : Q_yabizo α,
      encode (q_cuyaxe opA t) = q_cuyaxe opB (q_kayomo encode t) := by
  intro t
  induction t with
  | q_fevuca x => rfl
  | q_jiretu left right ihLeft ihRight =>
      simp only [q_cuyaxe, q_kayomo]
      rw [h, ihRight, ihLeft]

#print axioms solved_bridge

end S_tidolu
```
