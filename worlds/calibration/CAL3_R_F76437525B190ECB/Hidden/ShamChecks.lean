import World.Base
namespace P3.CAL3_R_F76437525B190ECB.ShamInterpretation
open Mark
abbrev Point := Int × Int

def action : Mark → Point → Point
  | a, (x, y) => (x + 1, y)
  | b, (x, y) => (x, y + 1)

def inverseAction : Mark → Point → Point
  | a, (x, y) => (x - 1, y)
  | b, (x, y) => (x, y - 1)

theorem action_inverse (m : Mark) (q : Point) : action m (inverseAction m q) = q := by
  cases m <;> cases q <;> simp [action, inverseAction]

theorem inverse_action (m : Mark) (q : Point) : inverseAction m (action m q) = q := by
  cases m <;> cases q <;> simp [action, inverseAction]

def run : List Mark → Point → Point
  | [], q => q
  | m :: w, q => run w (action m q)

def undo : List Mark → Point → Point
  | [], q => q
  | m :: w, q => inverseAction m (undo w q)

theorem run_append (u v : List Mark) (q : Point) : run (u ++ v) q = run v (run u q) := by
  induction u generalizing q with
  | nil => rfl
  | cons m u ih => exact ih (action m q)

theorem run_undo (w : List Mark) (q : Point) : run w (undo w q) = q := by
  induction w generalizing q with
  | nil => rfl
  | cons m w ih => simpa only [run, undo, action_inverse] using ih q

theorem undo_run (w : List Mark) (q : Point) : undo w (run w q) = q := by
  induction w generalizing q with
  | nil => rfl
  | cons m w ih => simp only [run, undo, ih, inverse_action]

theorem exchange_action (q : Point) : run [a, b] q = run [b, a] q := by
  cases q
  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)

theorem sham_incompatibility : run [a, b, a] (0, 1) ≠ run [b, a, b] (0, 1) := by decide

theorem sham_cannot_distinguish_visible (q : Point) : run [a, a, b, b, b, a] q = run [b, a, a, b, a, b] q := by
  cases q
  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)

theorem sham_cannot_distinguish_holdout1 (q : Point) : run [a, a, b, b, a, b, b, a] q = run [b, a, a, a, b, b, a, b] q := by
  cases q
  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)

theorem sham_cannot_distinguish_holdout2 (q : Point) : run [a, a, b, b, a, b, a, b] q = run [b, a, a, a, b, b, b, a] q := by
  cases q
  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)

end P3.CAL3_R_F76437525B190ECB.ShamInterpretation

#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.action_inverse
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.inverse_action
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.run_append
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.run_undo
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.undo_run
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.exchange_action
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.sham_incompatibility
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.sham_cannot_distinguish_visible
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.sham_cannot_distinguish_holdout1
#print axioms P3.CAL3_R_F76437525B190ECB.ShamInterpretation.sham_cannot_distinguish_holdout2
