import World.ChallengeEvaluation

namespace P3.CAL2_T2_9E9C8F0211D9DA4F

theorem hom_eval {α β : Type} (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_qijogi encode opA opB) :
    ∀ {n : Nat} (t : Q_tivugo α n) (env : ScopedIndex n → α),
      encode (q_yomuja opA env t) = q_yomuja opB (fun i => encode (env i)) (q_meduxi encode t) := by
  have h' : ∀ x y, encode (opA x y) = opB (encode x) (encode y) := h
  intro n t
  induction t with
  | q_zofije i => intro env; rfl
  | q_laduko a => intro env; rfl
  | q_karaka l r ihl ihr =>
      intro env
      show encode (opA (q_yomuja opA env l) (q_yomuja opA env r))
          = opB (q_yomuja opB (fun i => encode (env i)) (q_meduxi encode l))
              (q_yomuja opB (fun i => encode (env i)) (q_meduxi encode r))
      rw [h', ihl, ihr]
  | q_xiviyo v b ihv ihb =>
      intro env
      have key : (fun i => encode (q_wemiyu (q_yomuja opA env v) env i))
          = q_wemiyu (q_yomuja opB (fun i => encode (env i)) (q_meduxi encode v))
              (fun i => encode (env i)) := by
        funext i
        cases i with
        | first => exact ihv env
        | rest j => rfl
      show encode (q_yomuja opA (q_wemiyu (q_yomuja opA env v) env) b)
          = q_yomuja opB (q_wemiyu (q_yomuja opB (fun i => encode (env i)) (q_meduxi encode v))
              (fun i => encode (env i))) (q_meduxi encode b)
      rw [ihb, key]

theorem evaluation_solution : Holdout2Statement := by
  intro α β encode opA opB h n env a b c
  exact hom_eval encode opA opB h _ env

end P3.CAL2_T2_9E9C8F0211D9DA4F
