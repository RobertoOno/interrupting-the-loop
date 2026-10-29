import World.Base
namespace P3.CAL2_T2_9E9C8F0211D9DA4F
universe u v

theorem relevant_adapter_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_qijogi encode opA opB) {n : Nat} (t : Q_tivugo α n) :
    ∀ (envA : ScopedIndex n → α) (envB : ScopedIndex n → β),
      (∀ i, encode (envA i) = envB i) →
      encode (q_yomuja opA envA t) = q_yomuja opB envB (q_meduxi encode t) := by
  induction t with
  | q_zofije i =>
      intro envA envB related
      exact related i
  | q_laduko a =>
      intro envA envB related
      rfl
  | q_karaka left right ihLeft ihRight =>
      intro envA envB related
      simp only [q_yomuja, q_meduxi]
      rw [h, ihLeft envA envB related, ihRight envA envB related]
  | q_xiviyo value body ihValue ihBody =>
      intro envA envB related
      simp only [q_yomuja, q_meduxi]
      apply ihBody
      intro i
      cases i with
      | first => exact ihValue envA envB related
      | rest j => exact related j

end P3.CAL2_T2_9E9C8F0211D9DA4F
