from __future__ import division

import unittest

import numpy as np

import chainer
import chainer.testing
from chainer.training import extension
import chainermn
from chainermn.extensions import ObservationAggregator


class DummyChain(chainer.Chain):

    def __init__(self):
        super(DummyChain, self).__init__()

    def forward(self, x):
        return chainer.Variable(x, grad=np.array([0]))


class TestObservationAggregator(unittest.TestCase):

    def setUp(self):
        self.communicator = chainermn.create_communicator('naive')

    def test_observation_aggregator1(self):
        model = DummyChain()
        comm = self.communicator

        optimizer = chainermn.create_multi_node_optimizer(
            chainer.optimizers.Adam(), self.communicator)
        optimizer.setup(model)

        train = np.random.rand(10, 1)
        train_iter = chainer.iterators.SerialIterator(train,
                                                      batch_size=1,
                                                      repeat=True,
                                                      shuffle=True)

        updater = chainer.training.StandardUpdater(train_iter, optimizer)

        trainer = chainer.training.Trainer(updater, (1, 'epoch'))

        @extension.make_extension(
            trigger=(1, 'iteration'), priority=extension.PRIORITY_WRITER)
        def rank_reporter(trainer):
            trainer.observation['rank'] = comm.rank

        @extension.make_extension(
            trigger=(1, 'iteration'), priority=extension.PRIORITY_READER)
        def aggregated_rank_checker(trainer):
            actual = trainer.observation['rank-aggregated']
            expected = (comm.size - 1) / 2
            chainer.testing.assert_allclose(actual,
                                            expected)

        trainer.extend(rank_reporter)
        trainer.extend(ObservationAggregator(
            comm, 'rank', 'rank-aggregated', comm_trigger=(1, 'iteration')))
        trainer.extend(aggregated_rank_checker)

        trainer.run()

    def test_observation_aggregator2(self):
        model = DummyChain()
        comm = self.communicator

        optimizer = chainermn.create_multi_node_optimizer(
            chainer.optimizers.Adam(), self.communicator)
        optimizer.setup(model)

        train = np.random.rand(10, 1)
        train_iter = chainer.iterators.SerialIterator(train,
                                                      batch_size=1,
                                                      repeat=True,
                                                      shuffle=True)

        updater = chainer.training.StandardUpdater(train_iter, optimizer)

        trainer = chainer.training.Trainer(updater, (1, 'epoch'))

        @extension.make_extension(
            trigger=(1, 'iteration'), priority=extension.PRIORITY_WRITER)
        def rank_reporter(trainer):
            trainer.observation['rank'] = comm.rank + \
                trainer.updater.iteration % 2

        @extension.make_extension(
            trigger=(1, 'iteration'), priority=extension.PRIORITY_READER)
        def aggregated_rank_checker(trainer):
            if trainer.updater.iteration % 2 == 0:
                actual = trainer.observation['rank-aggregated']
                expected = (comm.size - 1) / 2 + 1 / 2
                chainer.testing.assert_allclose(actual,
                                                expected)

        trainer.extend(rank_reporter)
        trainer.extend(ObservationAggregator(
            comm, 'rank', 'rank-aggregated', comm_trigger=(2, 'iteration')))
        trainer.extend(aggregated_rank_checker)

        trainer.run()
