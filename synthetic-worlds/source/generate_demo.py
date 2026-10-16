"""Generate one synthetic world. No model/training code or clinical inputs."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from cores import CORES
from renderer import generate
from recipes import draw_recipe,seed,SPEC


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core',choices=list(CORES),default='switching')
    parser.add_argument('--draw',type=int,default=0)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();torch.set_num_threads(2)
    if args.draw<0:raise ValueError('Nonnegative draw required')
    args.out.mkdir(parents=True,exist_ok=False)
    entry=dict(contacts=[dict(source_row=r,source_col=c) for r in range(8) for c in range(16)])
    settings=draw_recipe('public',args.core,args.draw)
    cs=seed('public',args.core,args.draw,'core');rs=seed('public',args.core,args.draw,'renderer')
    def core(_rng,h,w):return CORES[args.core](np.random.default_rng(cs),h,w,frames=2560)
    result=generate(rs,entry,None,core=core,settings=settings)
    packet={}
    for b,band in enumerate(['slow','mid','fast']):
        for arm in range(2):
            packet[f'arm{arm}_{band}']=np.clip(result[3][f'arm{arm}_normalized_bins_{b}'][1024:].transpose(1,2,0),-15,15)
            packet[f'arm{arm}_raw_{band}']=result[3][f'arm{arm}_raw_bins_{b}'][1024:].transpose(1,2,0)
        packet[f'center_{band}']=result[3][f'control_bin_median_{b}']
        packet[f'scale_{band}']=result[3][f'control_bin_scale_{b}']
        packet[f'calibration_raw_{band}']=result[3][f'arm0_raw_bins_{b}'][:768].transpose(1,2,0)
    np.savez_compressed(args.out/'packet.npz',**packet)
    np.savez_compressed(args.out/'state.npz',**result[2])
    (args.out/'parameters.json').write_text(json.dumps(dict(core=args.core,draw=args.draw,core_seed=cs,renderer_seed=rs,parameters=result[4],spec=SPEC),indent=2))
    print('Generated synthetic content; no training launched:',args.out)


if __name__=='__main__':main()
