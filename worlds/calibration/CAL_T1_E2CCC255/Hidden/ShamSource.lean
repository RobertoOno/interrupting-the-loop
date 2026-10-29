namespace S_batopa

universe u

inductive Q_dimapu {α : Type u} (S : α → α → Prop) : α → α → Type u where
  | q_degutu (x : α) : Q_dimapu S x x
  | q_yitile {x y z : α} : S x y → Q_dimapu S y z → Q_dimapu S x z

def q_curahe {α : Type u} (S : α → α → Prop) (Q : α → Prop) : Prop :=
  ∀ (x y : α), S x y → Q y → Q x

theorem solved_bridge {α : Type u} {S : α → α → Prop} {Q : α → Prop}
    (h : q_curahe S Q) {x z : α}
    (route : Q_dimapu S x z) (hz : Q z) : Q x := by
  induction route with
  | q_degutu point => exact hz
  | q_yitile hxy tail ih => exact h _ _ hxy (ih hz)

#print axioms solved_bridge

end S_batopa
