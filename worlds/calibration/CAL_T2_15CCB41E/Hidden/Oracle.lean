import World.Base

namespace P3.CAL_T2_15CCB41E

universe u v

theorem oracle_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_dowole encode opA opB) :
    ∀ t : Q_jabika α,
      encode (q_zawasi opA t) = q_zawasi opB (q_docecu encode t) := by
  intro t
  induction t with
  | q_cobize x => rfl
  | q_dituca left right ihLeft ihRight =>
      simp only [q_zawasi, q_docecu]
      rw [h, ihLeft, ihRight]

end P3.CAL_T2_15CCB41E
