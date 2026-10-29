import World.Base

namespace P3.CAL_T2_15CCB41E

def witnessEncode (value : Unit) : Unit := value
def witnessOperation (_left _right : Unit) : Unit := ()

theorem nonvacuity : q_dowole witnessEncode witnessOperation witnessOperation := by
  intro x y
  cases x
  cases y
  rfl

#print axioms nonvacuity

end P3.CAL_T2_15CCB41E
