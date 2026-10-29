import World.Base
namespace P3.CAL2_T2_9E9C8F0211D9DA4F

def Holdout1Statement : Prop :=
  ∀ (α β : Type) (encode : α → β) (opA : α → α → α) (opB : β → β → β),
    q_qijogi encode opA opB → ∀ (n : Nat) (env : ScopedIndex n → α),
    ∀ (a b : Q_tivugo α n),
      encode (q_yomuja opA env (.q_karaka a b)) =
        q_yomuja opB (fun i => encode (env i)) (q_meduxi encode (.q_karaka a b))

end P3.CAL2_T2_9E9C8F0211D9DA4F
