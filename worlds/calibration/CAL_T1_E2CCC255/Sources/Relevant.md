# Solved source world

This independent world establishes transport over an arbitrary finite route.

```lean
namespace S_veqabo

universe u

inductive Q_cafuyu {α : Type u} (S : α → α → Prop) : α → α → Type u where
  | q_dikozo (x : α) : Q_cafuyu S x x
  | q_zeluxi {x y z : α} : S x y → Q_cafuyu S y z → Q_cafuyu S x z

def q_ducumu {α : Type u} (S : α → α → Prop) (Q : α → Prop) : Prop :=
  ∀ (x y : α), S x y → Q x → Q y

theorem solved_bridge {α : Type u} {S : α → α → Prop} {Q : α → Prop}
    (h : q_ducumu S Q) {x z : α}
    (route : Q_cafuyu S x z) (hx : Q x) : Q z := by
  induction route with
  | q_dikozo point => exact hx
  | q_zeluxi hxy tail ih => exact ih (h _ _ hxy hx)

#print axioms solved_bridge

end S_veqabo
```
