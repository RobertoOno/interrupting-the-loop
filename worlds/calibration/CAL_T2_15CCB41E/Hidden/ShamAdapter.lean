import World.Base

namespace P3.CAL_T2_15CCB41E

universe u v

theorem sham_adapter_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_dowole encode opA opB) :
    ∀ left right : Q_jabika α,
      encode (q_zawasi opA (.q_dituca left right)) =
        opB (q_zawasi opB (q_docecu encode right))
          (q_zawasi opB (q_docecu encode left)) := by
  intro left right
  simp only [q_zawasi]
  rw [h]

end P3.CAL_T2_15CCB41E
