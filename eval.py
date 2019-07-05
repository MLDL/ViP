import os
import sys
import datetime
import yaml
import torch
import torchvision
import numpy                    as np
import torch.nn                 as nn
import torch.optim              as optim
import torch.utils.data         as Data

from tensorboardX                       import SummaryWriter

from parse_args                         import Parse
from models.models_import               import create_model_object
from datasets                           import data_loader 
from losses                             import Losses
from metrics                            import Metrics
from checkpoint                         import save_checkpoint, load_checkpoint

def eval(**args):

    print('Experimental Setup: ',args)

    avg_acc = []

    for total_iteration in range(args['rerun']):
        d = datetime.datetime.today()
        date = d.strftime('%Y%m%d-%H%M%S')
        result_dir = os.path.join(args['save_dir'], args['model'], '_'.join((args['dataset'],'[exp]',date)))
        log_dir    = os.path.join(result_dir, 'logs')
        save_dir   = os.path.join(result_dir, 'checkpoints')

        os.makedirs(result_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True) 
        os.makedirs(save_dir, exist_ok=True) 

        with open(os.path.join(result_dir, 'config.yaml'),'w') as outfile:
            yaml.dump(args, outfile, default_flow_style=False)

        # Tensorboard Element
        writer = SummaryWriter()

        # Load Data
        loader = data_loader(**args)#['dataset'], args['batch_size'], args['load_type'])

        if args['load_type'] == 'valid':
            eval_loader = loader['valid']

        elif args['load_type'] == 'test':
            eval_loader  = loader['test'] 

        else:
            sys.exit('load_type must be valid or test for eval, exiting')

        # END IF

        # Check if GPU is available (CUDA)
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    
        # Load Network
        model = create_model_object(**args).to(device)

        if args['pretrained']:
            model.load_state_dict(torch.load(args['pretrained']))

        # Training Setup
        params     = [p for p in model.parameters() if p.requires_grad]

        #model_loss = Losses(**args)
        acc_metric = Metrics(**args, result_dir=result_dir, ndata=len(eval_loader.dataset))

        running_loss = 0.0
        acc = 0.0

        # Setup Model To Evaluate 
        model.eval()

        for step, data in enumerate(eval_loader):
            x_input = data['data'].to(device)
            outputs = model(x_input)

            acc = acc_metric.get_accuracy(outputs, data)

            #loss = model_loss.loss(outputs, data)
            #running_loss += loss.item()

            # Add Loss Element
            #writer.add_scalar(args['dataset']+'/'+args['model']+'/loss', loss.item(), epoch*len(eval_loader) + step)

            if np.isnan(running_loss):
                import pdb; pdb.set_trace()

            if step % 100 == 0:
                print('Step: {}/{} | {} loss: {:.4f}'.format(step, len(eval_loader), args['load_type'], running_loss/100.))
                running_loss = 0.0

        writer.add_scalar(args['dataset']+'/'+args['model']+'/'+args['load_type']+'_accuracy', acc)
        print('Accuracy of the network on the {} set: {:.3f} %\n'.format(args['load_type'], 100.*acc))
        # Close Tensorboard Element
        writer.close()

        avg_acc.append(acc)
    
    print('Average {} accuracy across {} runs is {}'.format(args['load_type'], args['rerun'], np.mean(avg_acc)))

if __name__ == '__main__':

    parse = Parse()
    args = parse.get_args()

    # For reproducibility
    torch.backends.cudnn.deterministic = True
    torch.manual_seed(args['seed'])
    np.random.seed(args['seed'])

    eval(**args)
