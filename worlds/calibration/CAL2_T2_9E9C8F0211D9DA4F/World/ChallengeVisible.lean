import World.Base
namespace P3.CAL2_T2_9E9C8F0211D9DA4F

def VisibleStatement : Prop :=
  ∀ (α β : Type) (encode : α → β) (opA : α → α → α) (opB : β → β → β),
    q_qijogi encode opA opB → ∀ (n : Nat) (env : ScopedIndex n → α),
    ∀ (a : Q_tivugo α n) (b : Q_tivugo α (Nat.succ n)),
      encode (q_yomuja opA env (.q_xiviyo a b)) =
        q_yomuja opB (fun i => encode (env i)) (q_meduxi encode (.q_xiviyo a b))

end P3.CAL2_T2_9E9C8F0211D9DA4F
