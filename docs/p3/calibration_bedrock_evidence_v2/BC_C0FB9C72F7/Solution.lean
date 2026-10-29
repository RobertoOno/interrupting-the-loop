import World.ChallengeEvaluation

namespace P3.CAL2_T1_6A99B5D87E404DF3

universe u

theorem sound {α : Type u} {R0 R1 R2 R3 R4 : α → α → Prop}
    {P : Q_jiburo → α → Prop} (h : Q_tumuho R0 R1 R2 R3 R4 P) :
    ∀ {s : Q_jiburo} {x : α} {f : Q_jiburo} {z : α},
      Q_gajayo R0 R1 R2 R3 R4 s x f z → P s x → P f z := by
  intro s x f z d
  induction d with
  | q_kebida m p => exact fun hp => hp
  | q_biluva hr _ ih => exact fun hp => ih (h.q_yuqipo _ _ hr hp)
  | q_jovobo hr _ ih => exact fun hp => ih (h.q_musiba _ _ hr hp)
  | q_temifa hr _ ih => exact fun hp => ih (h.q_fivigi _ _ hr hp)
  | q_yalaja hr _ ih => exact fun hp => ih (h.q_dociru _ _ hr hp)
  | q_kepeza hr _ ih => exact fun hp => ih (h.q_hudoju _ _ hr hp)
  | q_qarocu _ _ ih1 ih2 => exact fun hp => ih2 (ih1 hp)
  | q_civiva _ _ _ ih1 ih2 ih3 => exact fun hp => ih3 (ih2 (ih1 hp))

theorem evaluation_solution : Holdout1Statement := by
  intro α R0 R1 R2 R3 R4 P h x y z d1 d2 hp
  exact sound h d2 (sound h d1 hp)

end P3.CAL2_T1_6A99B5D87E404DF3
