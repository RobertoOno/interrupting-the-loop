import World.Base
namespace P3.CAL2_T2_9E9C8F0211D9DA4F
theorem sham_adapter_bridge (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β) (h : q_qijogi encode opA opB) :
    ∀ x y, encode (opA x y) = opB (encode y) (encode x) := by
  intro x y
  rw [h]
end P3.CAL2_T2_9E9C8F0211D9DA4F
