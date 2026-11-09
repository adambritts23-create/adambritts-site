"""Closed-loop rinse-water recovery. pip install idaes-pse highspy
Custom component-flow balance blocks in an IDAES flowsheet, solved with HiGHS.
No thermodynamic property package or predictive membrane/precipitation model.
All flows kg/h; Cr and Fe are elemental mass, salt is a lumped dissolved load.
"""
import json
from pathlib import Path
from pyomo.environ import ConcreteModel, Var, ConstraintList, Objective, NonNegativeReals, SolverFactory, value
from idaes.core import FlowsheetBlock
import idaes

FEED = dict(water=10000., salt=20., Cr=0.5, Fe=1.)
PASS = dict(water=.98, salt=1., Cr=.005, Fe=.01)
FILTER = dict(water=.995, salt=1., Cr=.1, Fe=.1)
RO = dict(water=.75, salt=.0075, Cr=.00075, Fe=.00075)
STREAMS = ['feed','mixed','clarified','sludge','filtered','cake','product','concentrate','recycle','purge']
def solve(recycle):
    m=ConcreteModel(); m.fs=FlowsheetBlock(dynamic=False)
    f=m.fs
    f.flow=Var(STREAMS,list(FEED),domain=NonNegativeReals)
    f.balance=ConstraintList()
    for c,feed in FEED.items():
        x=lambda s:f.flow[s,c]
        f.balance.add(x('feed')==feed)
        f.balance.add(x('mixed')==x('feed')+x('recycle'))
        f.balance.add(x('clarified')==PASS[c]*x('mixed'))
        f.balance.add(x('sludge')==x('mixed')-x('clarified'))
        f.balance.add(x('filtered')==FILTER[c]*x('clarified'))
        f.balance.add(x('cake')==x('clarified')-x('filtered'))
        f.balance.add(x('product')==RO[c]*x('filtered'))
        f.balance.add(x('concentrate')==x('filtered')-x('product'))
        f.balance.add(x('recycle')==recycle*x('concentrate'))
        f.balance.add(x('purge')==(1-recycle)*x('concentrate'))
    m.objective=Objective(expr=0)
    result=SolverFactory('appsi_highs').solve(m)
    assert str(result.solver.termination_condition)=='optimal'
    streams={s:{c:value(f.flow[s,c]) for c in FEED} for s in STREAMS}
    residual={c:sum(streams[s][c] for s in ['sludge','cake','product','purge'])-FEED[c] for c in FEED}
    assert max(map(abs,residual.values()))<1e-7
    return dict(recycle=recycle,streams=streams,residual=residual)
if __name__=='__main__':
    out=Path(__file__).with_name('reference.json')
    out.write_text(json.dumps(dict(engine='IDAES '+idaes.__version__+' / Pyomo / HiGHS',cases=[solve(i/100) for i in range(81)]),indent=2))
    print('81 recycle cases solved; all component balances close below 1e-7 kg/h. '+str(out))
