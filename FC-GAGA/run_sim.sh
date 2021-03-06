cp ../DC-RNN/data/sim/adj_mx.pkl ./data/sim/
for i in {0..99}
do
     python -m generate_training_data --output_dir=data/sim/ --traffic_df_filename=../data/stationary/h5/s$i.h5 --horizon=1 --history_length=1
    python train_test.py train sim
    # val sim (model index) (output file)
    python train_test.py val sim 0 data/sim/output/preds$i.npz
    rm model/sim-0.hdf5
    rm data/sim/*.npz
done