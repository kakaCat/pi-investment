# TODO/FIXME 清理计划

**生成时间**: /Users/yunpeng/pi-investment/quantsys-v2
**总数**: 8576 项

## 统计概览

### 按优先级

- 🔴 P1 (高优先级): 9 项
- 🟡 P2 (中优先级): 8429 项
- 🟢 P3 (低优先级): 138 项

### 按分类

- **立即修复**: 553 项
- **功能增强**: 95 项
- **技术债务**: 7790 项
- **文档完善**: 28 项
- **已废弃**: 110 项

## 清理策略

### 立即处理 (P1)

这些 TODO 影响功能完整性，应该立即修复或删除：

- [ ] `venv/lib/python3.13/site-packages/pydantic/json_schema.py:1394` - fixme - this is a workaround for the fact that we can't always resolve refs
- [ ] `venv/lib/python3.13/site-packages/opentelemetry/attributes/__init__.py:28` - Remove this workaround and revert to the simpler implementation
- [ ] `venv/lib/python3.13/site-packages/mlflow/tracking/client.py:3010` - The current implementation creates a temporary file. Consider adding
- [ ] `venv/lib/python3.13/site-packages/torch/masked/_ops.py:732` - temporary workaround for issue with bfloat16/float16 remove when acctype is implemented for scatter_reduce
- [ ] `venv/lib/python3.13/site-packages/torch/distributed/_composable/contract.py:234` - (@yhcharles): this is a temporary fix, need a better way
- [ ] `venv/lib/python3.13/site-packages/setuptools/config/setupcfg.py:105` - Temporary cast until mypy 1.12 is released with upstream fixes from typeshed
- [ ] `venv/lib/python3.13/site-packages/statsmodels/miscmodels/ordinal_model.py:595` - temporary, needs better fix, modelwc adds 1 by default
- [ ] `venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/gmm.py:514` - this is a temporary fix, need
- [ ] `venv/lib/python3.13/site-packages/statsmodels/base/tests/test_shrink_pickle.py:166` - temporary, fixed in main

### 本周处理 (P2 中的立即修复和技术债务)

- [ ] `live_trading/execute_v14_rebalance_fixed.py:128` - 调用trader.sell()方法
- [ ] `live_trading/execute_v14_rebalance_fixed.py:139` - 调用trader.buy()方法
- [ ] `live_trading/test_v14_rebalance.py:119` - 这里需要调用trader的buy方法执行买入
- [ ] `scripts/migrate_print_to_logger.py:204` - migrate print → logger')
- [ ] `adapters/inbound/fastapi_app/exception_handlers.py:66` - Integrate with alerting system (PagerDuty, etc.)
- [ ] `adapters/inbound/fastapi_app/exception_handlers.py:149` - Integrate with alerting system
- [ ] `adapters/inbound/fastapi_app/routes/market_async.py:184` - 添加时间戳
- [ ] `adapters/inbound/fastapi_app/routes/pools.py:60` - 接入实际 Service
- [ ] `adapters/inbound/fastapi_app/routes/pools.py:85` - 接入实际 Service
- [ ] `adapters/inbound/fastapi_app/routes/pools.py:104` - 接入实际 Service

*还有 8324 项...*

### 转为 GitHub Issue (P2 功能增强)

- [ ] `tools/backfill_factors.py:104` - 检查该股票+日期是否已有因子数据（优化：批量查询）
- [ ] `venv/lib/python3.13/site-packages/highspy/highs.py:1283` - Mapping support with constraint names can be improved, e.g., by allowing a name collection to be passed
- [ ] `venv/lib/python3.13/site-packages/fastapi/routing.py:2546` - deprecate this once the lifespan (or alternative) interface is improved
- [ ] `venv/lib/python3.13/site-packages/fastapi/routing.py:6363` - remove this once the lifespan (or alternative) interface is improved
- [ ] `venv/lib/python3.13/site-packages/fastapi/routing.py:6379` - remove this once the lifespan (or alternative) interface is improved

*还有 90 项...*

### 直接删除 (已废弃)

- [ ] `venv/lib/python3.13/site-packages/backtrader/feed.py:190` - These two are never used and could be removed
- [ ] `venv/lib/python3.13/site-packages/backtrader/feed.py:769` - if removed from guest, remove here too
- [ ] `venv/lib/python3.13/site-packages/torchgen/gen.py:2815` - --op-registration-whitelist will be removed when all call-sites
- [ ] `venv/lib/python3.13/site-packages/pydantic/mypy.py:820` - this path should be removed (see https://github.com/pydantic/pydantic/issues/11119)
- [ ] `venv/lib/python3.13/site-packages/pydantic/main.py:4` - v3 fallback to `dict` when the deprecated `dict` method gets removed.
- [ ] `venv/lib/python3.13/site-packages/gymnasium/wrappers/jax_to_torch.py:90` - Device was part of the public API, but should be removed in favor of _env_device and
- [ ] `venv/lib/python3.13/site-packages/cvxpy/expressions/expression.py:740` - remove special case once CPP backend is removed
- [ ] `venv/lib/python3.13/site-packages/cvxpy/expressions/expression.py:743` - cleanup once CPP backend is removed
- [ ] `venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/from_array_to_matrix.py:448` - check if subremoved should be permuted as well...
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_stochastic_process.py:77` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_stochastic_process.py:109` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_stochastic_process.py:408` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_continuous_rv.py:677` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_continuous_rv.py:1348` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_continuous_rv.py:1358` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_mix.py:80` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/sympy/stats/tests/test_compound_rv.py:90` - Restore tests once warnings are removed
- [ ] `venv/lib/python3.13/site-packages/llvmlite/binding/typeref.py:7` - Remove `opaque_pointers_enabled' when TP's are removed.
- [ ] `venv/lib/python3.13/site-packages/llvmlite/binding/typeref.py:115` - Remove me once typed pointers support is removed.
- [ ] `venv/lib/python3.13/site-packages/llvmlite/binding/typeref.py:229` - Remove me once typed pointers support is removed.
- [ ] `venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otBase.py:1011` - Following hack to be removed by rewriting how FormatSwitching tables
- [ ] `venv/lib/python3.13/site-packages/mlflow/gateway/app.py:330` - Remove the deprecated endpoint
- [ ] `venv/lib/python3.13/site-packages/mlflow/gateway/app.py:382` - Remove the deprecated endpoint
- [ ] `venv/lib/python3.13/site-packages/torch/distributed/distributed_c10d.py:2212` - once UCC plugin is fully deprecated, remove
- [ ] `venv/lib/python3.13/site-packages/torch/fx/proxy.py:165` - deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/fx/proxy.py:166` - deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/fx/proxy.py:237` - node_name_to_scope will be deprecated in favor of
- [ ] `venv/lib/python3.13/site-packages/torch/_inductor/codecache.py:684` - pickler.fast is technically deprecated. Will this work on new python versions?
- [ ] `venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py:1373` - (justinchuby): Looks like this op is deprecated in torch
- [ ] `venv/lib/python3.13/site-packages/torch/distributed/_local_tensor/__init__.py:1537` - This should either be removed or documented why it's necessary.
- [ ] `venv/lib/python3.13/site-packages/torch/distributed/_local_tensor/__init__.py:1551` - This should either be removed or documented why it's necessary.
- [ ] `venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_pointwise_ops.py:395` - positive should be removed once CIA (Copy Is All) optimizes it away.
- [ ] `venv/lib/python3.13/site-packages/torch/fx/experimental/optimization.py:178` - Determine whether this can be removed after type inference.
- [ ] `venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/triton.py:2891` - (coconutruben): deprecate once autoheuristic is deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/triton.py:3198` - (coconutruben): deprecate once autoheuristic is deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_typing.py:16` - Use TypeAlias when Python 3.6 is deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/testing/_internal/common_nn.py:2821` - This code can path can be removed if #61309 is resolved
- [ ] `venv/lib/python3.13/site-packages/torch/_dynamo/variables/object_protocol.py:1641` - can trace this once TypingVariable is removed
- [ ] `venv/lib/python3.13/site-packages/torch/_dynamo/variables/torch.py:3823` - [@lucaskabela]: Remove the behavior below since it is deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/ao/quantization/qconfig.py:52` - deprecated, remove
- [ ] `venv/lib/python3.13/site-packages/torch/ao/quantization/fx/quantize_handler.py:219` - not used, can be removed after torch.ao.quantization namespace is deprecated
- [ ] `venv/lib/python3.13/site-packages/torch/ao/quantization/fx/quantize_handler.py:224` - not used, can be removed after torch.ao.quantization namespace is deprecated
- [ ] `venv/lib/python3.13/site-packages/sqlalchemy/orm/query.py:560` - this event needs to be deprecated, as it currently applies
- [ ] `venv/lib/python3.13/site-packages/numpy/fft/__init__.py:204` - `numpy.fft.helper`` was deprecated in NumPy 2.0. It should
- [ ] `venv/lib/python3.13/site-packages/pip/_internal/build_env/base.py:26` - simplify this data model when the legacy subprocess installer is removed
- [ ] `venv/lib/python3.13/site-packages/sklearn/metrics/_scorer.py:317` - (1.11): remove this when sample_weight is removed from the `__call__`
- [ ] `venv/lib/python3.13/site-packages/sklearn/metrics/pairwise.py:2022` - below 2 lines can be removed once min scipy >= 1.14. Support for
- [ ] `venv/lib/python3.13/site-packages/sklearn/tests/test_common.py:270` - As more modules support get_feature_names_out they should be removed
- [ ] `venv/lib/python3.13/site-packages/sklearn/tests/test_base.py:246` - (1.11): remove svc test for predict_proba after it is deprecated
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/_logistic.py:1994` - (1.11): remove this when sample_weight as positional arg is removed
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/_logistic.py:2515` - (1.11): remove this when sample_weight is removed from the `score`
- [ ] `venv/lib/python3.13/site-packages/sklearn/utils/_plotting.py:185` - Remove once kwargs deprecated on all displays
- [ ] `venv/lib/python3.13/site-packages/sklearn/preprocessing/_target_encoder.py:238` - (1.11) remove `shuffle` and `random_state` params, which had been deprecated
- [ ] `venv/lib/python3.13/site-packages/sklearn/model_selection/_validation.py:62` - (SLEP6): To be removed when set_config(enable_metadata_routing=False) is not
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:269` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:333` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:348` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:831` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:927` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:1473` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:2019` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:2443` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:2472` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py:2748` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_score_objects.py:1445` - remove when enable_metadata_routing is deprecated
- [ ] `venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_common_curve_display.py:263` - Clean-up once `estimator_name` deprecated in all displays
- [ ] `venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_common_curve_display.py:308` - Clean-up once `estimator_name` deprecated in all displays
- [ ] `venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py:161` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py:1835` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py:1879` - (1.11): remove the deprecated friedman_mse criterion parametrization
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py:434` - (1.12): remove deprecated use_legacy_attributes
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py:658` - (1.12): remove deprecated use_legacy_attributes
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py:2662` - (1.10): use_legacy_attributes gets deprecated
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py:2701` - (1.10): remove this test when n_jobs gets removed
- [ ] `venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py:2843` - (1.10): remove when penalty is removed
- [ ] `venv/lib/python3.13/site-packages/sklearn/utils/tests/test_plotting.py:199` - Remove once kwargs deprecated on all displays
- [ ] `venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_discretization.py:531` - this check is redundant with common checks and can be removed
- [ ] `venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_file_loader.py:80` - (#1711): Find non-deprecated replacement for tf_record_iterator.
- [ ] `venv/lib/python3.13/site-packages/setuptools/config/_apply_pyprojecttoml.py:352` - remove check when `bdist_wheel` has been fully removed from pypa/wheel
- [ ] `venv/lib/python3.13/site-packages/setuptools/tests/test_editable_install.py:1097` - Remove tests after _run_build_steps is removed.
- [ ] `venv/lib/python3.13/site-packages/pydantic/_internal/_generate_schema.py:2559` - V3: this function is only used for deprecated decorators. It should
- [ ] `venv/lib/python3.13/site-packages/pydantic/_internal/_decorators.py:263` - most likely this branch can be removed when we drop support for Python 3.12:
- [ ] `venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_estimating_equations.py:1946` - alias to be removed, temporary backwards compatibility
- [ ] `venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_estimating_equations.py:2305` - alias to be removed, temporary backwards compatibility
- [ ] `venv/lib/python3.13/site-packages/statsmodels/gam/tests/test_gam.py:529` - Mean has to be removed
- [ ] `venv/lib/python3.13/site-packages/statsmodels/gam/tests/test_gam.py:535` - Mean has to be removed
- [ ] `venv/lib/python3.13/site-packages/statsmodels/genmod/families/links.py:1292` - Deprecated aliases, remove after 0.15
- [ ] `venv/lib/python3.13/site-packages/scipy/sparse/_construct.py:670` - delete next 15 lines [combine with _eye()] once spmatrix removed
- [ ] `venv/lib/python3.13/site-packages/scipy/sparse/_construct.py:816` - delete this if-clause and replace _sparse with _array when spmatrix removed
- [ ] `venv/lib/python3.13/site-packages/scipy/sparse/_construct.py:960` - delete this if-clause and replace _sparse with _array when spmatrix removed
- [ ] `venv/lib/python3.13/site-packages/scipy/sparse/_construct.py:1035` - remove this if-structure when sparse matrices removed
- [ ] `venv/lib/python3.13/site-packages/scipy/integrate/_ivp/bdf.py:289` - switch to csc_array after spmatrix is removed
- [ ] `venv/lib/python3.13/site-packages/scipy/integrate/_ivp/radau.py:328` - use I = eye_array(self.n, format="csc") after spmatrix removed
- [ ] `venv/lib/python3.13/site-packages/scipy/integrate/_ivp/radau.py:379` - Use csc_array after spmatrix removed
- [ ] `venv/lib/python3.13/site-packages/pandas/core/generic.py:7101` - (3.0): once downcast is removed, we can do the .T
- [ ] `venv/lib/python3.13/site-packages/pandas/core/series.py:2685` - (3.0): this catching/filtering can be removed
- [ ] `venv/lib/python3.13/site-packages/pandas/core/series.py:2769` - (3.0): this catching/filtering can be removed
- [ ] `venv/lib/python3.13/site-packages/pandas/core/series.py:5428` - (3.0): this can be removed once GH#33302 deprecation is enforced
- [ ] `venv/lib/python3.13/site-packages/pandas/core/frame.py:4057` - (CoW): can be removed if/when we are always Copy-on-Write
- [ ] `venv/lib/python3.13/site-packages/pandas/core/dtypes/dtypes.py:2271` - (arrow#33642): This can be removed once supported by pyarrow
- [ ] `venv/lib/python3.13/site-packages/pandas/core/dtypes/common.py:1657` - warnings.catch_warnings can be removed when numpy>2.3.0
- [ ] `venv/lib/python3.13/site-packages/pandas/core/computation/expr.py:547` - (py314): deprecated since Python 3.8. Remove after Python 3.14 is min
- [ ] `venv/lib/python3.13/site-packages/pandas/core/computation/expr.py:551` - (py314): deprecated since Python 3.8. Remove after Python 3.14 is min
- [ ] `venv/lib/python3.13/site-packages/pandas/core/computation/expr.py:558` - (py314): deprecated since Python 3.8. Remove after Python 3.14 is min
- [ ] `venv/lib/python3.13/site-packages/pandas/core/arrays/base.py:2170` - (3.0): this can be removed once GH#33302 deprecation is enforced
- [ ] `venv/lib/python3.13/site-packages/pandas/core/indexes/base.py:4227` - (GH#50617): once Series.__[gs]etitem__ is removed we should be able
- [ ] `venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_astype.py:137` - (infer_string) this test can be removed after 3.0 (once str is the default)
- [ ] `venv/lib/python3.13/site-packages/pandas/tests/plotting/test_series.py:983` - (3.0): this can be removed once Period[B] deprecation is enforced
- [ ] `venv/lib/python3.13/site-packages/pandas/tests/plotting/frame/test_frame.py:2604` - (3.0): this can be removed once Period[B] deprecation is enforced
- [ ] `venv/lib/python3.13/site-packages/pandas/tests/indexes/period/test_indexing.py:720` - this test used to test get_value, which is removed in 2.0.

## 详细列表


### venv/lib/python3.13/site-packages/pydantic/json_schema.py

🔴 **L1394** [立即修复]: fixme - this is a workaround for the fact that we can't always resolve refs


### venv/lib/python3.13/site-packages/opentelemetry/attributes/__init__.py

🔴 **L28** [立即修复]: Remove this workaround and revert to the simpler implementation


### venv/lib/python3.13/site-packages/mlflow/tracking/client.py

🔴 **L3010** [立即修复]: The current implementation creates a temporary file. Consider adding


### venv/lib/python3.13/site-packages/torch/masked/_ops.py

🔴 **L732** [立即修复]: temporary workaround for issue with bfloat16/float16 remove when acctype is implemented for scatter_reduce


### venv/lib/python3.13/site-packages/torch/distributed/_composable/contract.py

🔴 **L234** [立即修复]: (@yhcharles): this is a temporary fix, need a better way


### venv/lib/python3.13/site-packages/setuptools/config/setupcfg.py

🔴 **L105** [立即修复]: Temporary cast until mypy 1.12 is released with upstream fixes from typeshed


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/ordinal_model.py

🔴 **L595** [立即修复]: temporary, needs better fix, modelwc adds 1 by default


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/gmm.py

🔴 **L514** [立即修复]: this is a temporary fix, need


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_shrink_pickle.py

🔴 **L166** [立即修复]: temporary, fixed in main


### tools/backfill_factors.py

🟡 **L104** [功能增强]: 检查该股票+日期是否已有因子数据（优化：批量查询）


### venv/lib/python3.13/site-packages/highspy/highs.py

🟡 **L1283** [功能增强]: Mapping support with constraint names can be improved, e.g., by allowing a name collection to be passed


### venv/lib/python3.13/site-packages/fastapi/routing.py

🟡 **L2546** [功能增强]: deprecate this once the lifespan (or alternative) interface is improved

🟡 **L6363** [功能增强]: remove this once the lifespan (or alternative) interface is improved

🟡 **L6379** [功能增强]: remove this once the lifespan (or alternative) interface is improved

🟡 **L6395** [功能增强]: remove this once the lifespan (or alternative) interface is improved


### venv/lib/python3.13/site-packages/pydantic/json_schema.py

🟡 **L1190** [功能增强]: improvements along with https://github.com/pydantic/pydantic/issues/8208


### venv/lib/python3.13/site-packages/git/util.py

🟡 **L586** [功能增强]: Support for Python 3.5 has been dropped, so these overloads can be improved.


### venv/lib/python3.13/site-packages/_pytest/python.py

🟡 **L306** [功能增强]: Improve the type of `parent` such that assert/ignore aren't needed.


### venv/lib/python3.13/site-packages/finrl/agents/stablebaselines3/hyperparams_opt.py

🟡 **L601** [功能增强]: optimize the alive_bonus_offset too


### venv/lib/python3.13/site-packages/river/linear_model/test_glm.py

🟡 **L55** [功能增强]: check momentum optimizers


### venv/lib/python3.13/site-packages/sympy/core/numbers.py

🟡 **L1456** [功能增强]: this can probably be optimized more


### venv/lib/python3.13/site-packages/sympy/polys/modulargcd.py

🟡 **L796** [功能增强]: to improve performance, choose the main variable here


### venv/lib/python3.13/site-packages/sympy/solvers/solvers.py

🟡 **L359** [功能增强]: improve solution testing


### venv/lib/python3.13/site-packages/sympy/combinatorics/fp_groups.py

🟡 **L870** [功能增强]: : Sims points out in [Sim94] that performance can be improved by


### venv/lib/python3.13/site-packages/sympy/tensor/tensor.py

🟡 **L3064** [功能增强]: this could be optimized by only swapping the indices

🟡 **L4563** [功能增强]: can be improved:


### venv/lib/python3.13/site-packages/sympy/tensor/indexed.py

🟡 **L89** [功能增强]: (some ideas for improvement)


### venv/lib/python3.13/site-packages/sympy/series/tests/test_formal.py

🟡 **L441** [功能增强]: rsolve needs improvement


### venv/lib/python3.13/site-packages/sympy/physics/quantum/cg.py

🟡 **L486** [功能增强]: Improve simplification method


### venv/lib/python3.13/site-packages/sympy/physics/quantum/gate.py

🟡 **L242** [功能增强]: This can be optimized to reduce the number of Qubit


### venv/lib/python3.13/site-packages/mpmath/libmp/gammazeta.py

🟡 **L1160** [功能增强]: optimize / cleanup interface / unify with list_primes


### venv/lib/python3.13/site-packages/mpmath/libmp/libelefun.py

🟡 **L1249** [功能增强]: optimize division precision


### venv/lib/python3.13/site-packages/mpmath/libmp/libmpi.py

🟡 **L124** [功能增强]: optimize

🟡 **L631** [功能增强]: optimize for real/imag cases

🟡 **L643** [功能增强]: optimize for real/imag cases


### venv/lib/python3.13/site-packages/google/protobuf/text_format.py

🟡 **L482** [功能增强]: refactor and optimize if this becomes an issue.


### venv/lib/python3.13/site-packages/jedi/inference/names.py

🟡 **L121** [功能增强]: improve the situation for when level is present.


### venv/lib/python3.13/site-packages/fontTools/subset/__init__.py

🟡 **L1250** [功能增强]: Can we improve this?

🟡 **L1285** [功能增强]: Can we improve this?

🟡 **L1314** [功能增强]: Can we improve this?


### venv/lib/python3.13/site-packages/fontTools/ttLib/ttGlyphSet.py

🟡 **L120** [功能增强]: Optimize by using instancer.setLocation()


### venv/lib/python3.13/site-packages/mlflow/pytorch/_lightning_autolog.py

🟡 **L250** [功能增强]: For logging optimizer params - Following scenarios are to revisited.


### venv/lib/python3.13/site-packages/mlflow/metrics/genai/model_utils.py

🟡 **L48** [功能增强]: improve this name


### venv/lib/python3.13/site-packages/mlflow/store/tracking/sqlalchemy_store.py

🟡 **L9748** [功能增强]: we should improve this by saving only the attributes into the table.


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/scan.py

🟡 **L889** [功能增强]: torch.flip copies the tensor, we should optimize it away


### venv/lib/python3.13/site-packages/torch/_functorch/apis.py

🟡 **L354** [功能增强]: Improve the return type of this function

🟡 **L467** [功能增强]: Improve the return type of this function


### venv/lib/python3.13/site-packages/torch/_functorch/aot_autograd.py

🟡 **L1936** [功能增强]: Improve the descs here with pytree information


### venv/lib/python3.13/site-packages/torch/_inductor/ops_handler.py

🟡 **L299** [功能增强]: Improve the description with some pseudocode


### venv/lib/python3.13/site-packages/torch/_inductor/lowering.py

🟡 **L9040** [功能增强]: Optimize to process pairs (pack=2) by creating a custom Pointwise


### venv/lib/python3.13/site-packages/torch/_inductor/virtualized.py

🟡 **L198** [功能增强]: improve type


### venv/lib/python3.13/site-packages/torch/_dynamo/comptime.py

🟡 **L308** [功能增强]: improve print format, current guard format is extremely


### venv/lib/python3.13/site-packages/torch/profiler/_pattern_matcher.py

🟡 **L492** [功能增强]: We should also check if the optimizer's numerical behavior will change.


### venv/lib/python3.13/site-packages/torch/export/unflatten.py

🟡 **L1641** [功能增强]: Can be optimized by adding submodules ahead of time.


### venv/lib/python3.13/site-packages/torch/_functorch/_activation_checkpointing/knapsack.py

🟡 **L82** [功能增强]: (chilli): I think if needed, this memory can be optimized with sliding


### venv/lib/python3.13/site-packages/torch/nn/modules/pooling.py

🟡 **L1311** [功能增强]: (by @ssnl): Improve adaptive pooling docs: specify what the input and


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py

🟡 **L2908** [功能增强]: (justinchuby): Get rid of the try catch here to improve readability


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/optimizer.py

🟡 **L50** [功能增强]: Update docstrings for optimizer.py


### venv/lib/python3.13/site-packages/torch/distributed/optim/optimizer.py

🟡 **L61** [功能增强]: (wanchaol): remove/merge this with ScriptLocalOptimizer once

🟡 **L113** [功能增强]: improve error propagation


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_state_dict_utils.py

🟡 **L620** [功能增强]: Improve unittesting for state_dict finetuning


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_runtime_utils.py

🟡 **L980** [功能增强]: (rohan-varma): When CPU offload and optimizer overlap,

🟡 **L1101** [功能增强]: (rohan-varma): this also waits for the overlapped optimizer step to finish


### venv/lib/python3.13/site-packages/torch/distributed/nn/jit/templates/remote_module_template.py

🟡 **L61** [功能增强]: Merge these two templates together in the future once TorchScript syntax is improved.


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharding_spec/_internals.py

🟡 **L181** [功能增强]: Can we improve this error message to point out the gaps?


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_math_ops.py

🟡 **L738** [功能增强]: The diagonal ops can have an improved sharding strategy for


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_view_ops.py

🟡 **L1405** [功能增强]: optimize this. we shouldn't simply blindly replicate


### venv/lib/python3.13/site-packages/torch/backends/_nnapi/serializer.py

🟡 **L511** [功能增强]: Improve this error message, possibly after converting


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/triton_heuristics.py

🟡 **L4785** [功能增强]: (jansel): we should be able to improve these heuristics


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/triton.py

🟡 **L1628** [功能增强]: Optimize - We don't need both operands to be zeroed except NaN * 0


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_optimizers.py

🟡 **L534** [功能增强]: consider tensor LR! See multi_tensor_optimizer_configs in test_optim.py --> tensor LR should work


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_methods_invocations.py

🟡 **L23189** [功能增强]: improve precision

🟡 **L23230** [功能增强]: improve precision

🟡 **L23267** [功能增强]: improve precision

🟡 **L23343** [功能增强]: improve precision

🟡 **L23448** [功能增强]: improve precision

🟡 **L27253** [功能增强]: improve precision

🟡 **L27299** [功能增强]: improve precision

🟡 **L27354** [功能增强]: improve precision

🟡 **L27375** [功能增强]: improve precision


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/_masked.py

🟡 **L459** [功能增强]: improve precision


### venv/lib/python3.13/site-packages/torch/_dynamo/backends/tvm.py

🟡 **L111** [功能增强]: (shingjan): This could be replaced by tvm.contrib.torch.optimize_torch


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/functions.py

🟡 **L2384** [功能增强]: improve trace_rules reasoning to provide better hints.


### venv/lib/python3.13/site-packages/torch/_dynamo/repro/after_dynamo.py

🟡 **L205** [功能增强]: improve these names with FQN


### venv/lib/python3.13/site-packages/torch/_dynamo/repro/after_aot.py

🟡 **L699** [功能增强]: improve these names with FQN


### venv/lib/python3.13/site-packages/torch/ao/quantization/utils.py

🟡 **L27** [功能增强]: (future PR): improve this.


### venv/lib/python3.13/site-packages/numpy/_core/_methods.py

🟡 **L89** [功能增强]: Optimize case when `where` is broadcast along a non-reduction


### venv/lib/python3.13/site-packages/sklearn/datasets/_arff_parser.py

🟡 **L68** [功能增强]: improve for efficiency


### venv/lib/python3.13/site-packages/sklearn/tests/test_docstrings.py

🟡 **L205** [功能增强]: this detection can be improved. Currently we assume that we have


### venv/lib/python3.13/site-packages/sklearn/linear_model/_coordinate_descent.py

🟡 **L2796** [功能增强]: improve


### venv/lib/python3.13/site-packages/narwhals/testing/asserts/series.py

🟡 **L293** [功能增强]: (FBruzzesi): Improve error message?


### venv/lib/python3.13/site-packages/numba/tests/test_parfors_passes.py

🟡 **L42** [功能增强]: refactor this with get_optimized_numba_ir() where this is


### venv/lib/python3.13/site-packages/polars/datatypes/convert.py

🟡 **L294** [功能增强]: further-improve handling for nested types (such as List,Struct)


### venv/lib/python3.13/site-packages/statsmodels/regression/linear_model.py

🟡 **L2141** [功能增强]: Could be improved, and may fail depending on scale of


### venv/lib/python3.13/site-packages/statsmodels/stats/proportion.py

🟡 **L995** [功能增强]: add continuity correction or other improvements for small samples


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/gmm.py

🟡 **L138** [功能增强]: this uses "textbook" calculation, improve linalg


### venv/lib/python3.13/site-packages/statsmodels/treatment/tests/test_teffects.py

🟡 **L93** [功能增强]: check if improved optimization brings values closer


### venv/lib/python3.13/site-packages/statsmodels/distributions/copula/archimedean.py

🟡 **L304** [功能增强]: check expm1 and log1p for improved numerical precision


### venv/lib/python3.13/site-packages/scipy/fft/_duccfft/basic.py

🟡 **L82** [功能增强]: Optimize for hermitian and real?

🟡 **L194** [功能增强]: Optimize for hermitian and real?


### venv/lib/python3.13/site-packages/functorch/dim/__init__.py

🟡 **L543** [功能增强]: optimize pytree here


### venv/lib/python3.13/site-packages/pandas/core/_numba/executor.py

🟡 **L233** [功能增强]: Optimize this


### venv/lib/python3.13/site-packages/pandas/tests/io/json/test_pandas.py

🟡 **L250** [功能增强]: create a better frame to test with and improve coverage

🟡 **L285** [功能增强]: improve coverage with date_format parameter


### live_trading/execute_v14_rebalance_fixed.py

🟡 **L128** [技术债务]: 调用trader.sell()方法

🟡 **L139** [技术债务]: 调用trader.buy()方法


### live_trading/test_v14_rebalance.py

🟡 **L119** [技术债务]: 这里需要调用trader的buy方法执行买入


### scripts/migrate_print_to_logger.py

🟡 **L204** [技术债务]: migrate print → logger')


### adapters/inbound/fastapi_app/exception_handlers.py

🟡 **L66** [技术债务]: Integrate with alerting system (PagerDuty, etc.)

🟡 **L149** [技术债务]: Integrate with alerting system


### adapters/inbound/fastapi_app/routes/market_async.py

🟡 **L184** [技术债务]: 添加时间戳


### adapters/inbound/fastapi_app/routes/pools.py

🟡 **L60** [技术债务]: 接入实际 Service

🟡 **L85** [技术债务]: 接入实际 Service

🟡 **L104** [技术债务]: 接入实际 Service

🟡 **L127** [技术债务]: 接入实际 Service


### adapters/inbound/fastapi_app/routes/v14_trading.py

🟡 **L180** [技术债务]: 从数据库查询历史净值数据


### adapters/inbound/fastapi_app/routes/stock_async.py

🟡 **L180** [技术债务]: (P-sentiment): sentiment 域迁移时将此端点并入 sentiment_async 并去重。


### adapters/inbound/fastapi_app/routes/analysis_async.py

🟡 **L1107** [技术债务]: 从信号表查询


### adapters/inbound/fastapi_app/routes/realtime_signals_async.py

🟡 **L312** [技术债务]: 集成飞书/企业微信推送


### adapters/outbound/datasources/providers/quantlib/factory.py

🟡 **L21** [技术债务]: 配置系统重构

🟡 **L42** [技术债务]: 配置系统重构后从配置读取


### adapters/outbound/datasources/providers/dividend/akshare.py

🟡 **L67** [技术债务]: Extract logic from services/dividend_service.py when refactoring Phase 3

🟡 **L81** [技术债务]: Extract logic from services/dividend_service.py when refactoring Phase 3


### scripts/refactor/batch_refactor_imports.py

🟡 **L102** [技术债务]: Refactor to: {suggested}\n{original}")


### venv/lib/python3.13/site-packages/typing_extensions.py

🟡 **L3457** [技术债务]: Use inspect.VALUE here, and make the annotations lazily evaluated


### venv/lib/python3.13/site-packages/packaging/tags.py

🟡 **L664** [技术债务]: Need to care about 32-bit PPC for ppc64 through 10.2?


### venv/lib/python3.13/site-packages/packaging/metadata.py

🟡 **L220** [技术债务]: The spec doesn't say anything about if the keys should be

🟡 **L945** [技术债务]: 2.1: can be in body


### venv/lib/python3.13/site-packages/packaging/version.py

🟡 **L434** [技术债务]: remove "no cover" when Python 3.9 is dropped.


### venv/lib/python3.13/site-packages/packaging/requirements.py

🟡 **L75** [技术债务]: Can we test whether something is contained within a requirement?

🟡 **L78** [技术债务]: Can we normalize the name and extra name?


### venv/lib/python3.13/site-packages/aiohttp/web_response.py

🟡 **L59** [技术债务]: (py311): Convert to StrEnum for wider use

🟡 **L292** [技术债务]: do we need domain/path here?


### venv/lib/python3.13/site-packages/aiohttp/web_exceptions.py

🟡 **L213** [技术债务]: this should include a date or etag header


### venv/lib/python3.13/site-packages/aiohttp/web.py

🟡 **L309** [技术债务]: (PY311): Use Unpack


### venv/lib/python3.13/site-packages/aiohttp/streams.py

🟡 **L283** [技术债务]: size is ignored, remove the param later

🟡 **L444** [技术债务]: should be `if` instead of `while`

🟡 **L456** [技术债务]: should be `if` instead of `while`

🟡 **L633** [技术债务]: add async def readuntil


### venv/lib/python3.13/site-packages/aiohttp/compression_utils.py

🟡 **L28** [技术债务]: (PY314): Remove mentions of backports.zstd across codebase


### venv/lib/python3.13/site-packages/aiohttp/web_urldispatcher.py

🟡 **L526** [技术债务]: impl missing abstract methods

🟡 **L600** [技术债务]: cache file content

🟡 **L611** [技术债务]: sha256 can be configurable param


### venv/lib/python3.13/site-packages/aiohttp/client_proto.py

🟡 **L137** [技术债务]: log this somehow?

🟡 **L213** [技术债务]: actual types are:


### venv/lib/python3.13/site-packages/aiohttp/formdata.py

🟡 **L170** [技术债务]: cgi.FieldStorage doesn't likes body parts with


### venv/lib/python3.13/site-packages/aiohttp/client_exceptions.py

🟡 **L386** [技术债务]: If we require ssl in future, this can become ssl.CertificateError


### venv/lib/python3.13/site-packages/aiohttp/helpers.py

🟡 **L284** [技术债务]: (PY311): username = login or account

🟡 **L290** [技术债务]: (PY311): Remove this, as password will be empty string


### venv/lib/python3.13/site-packages/truststore/_macos.py

🟡 **L558** [技术债务]: Not sure if we need the SecTrustResultType for anything?


### venv/lib/python3.13/site-packages/cycler/__init__.py

🟡 **L252** [技术债务]: : maybe add numpy style fancy slicing

🟡 **L434** [技术债务]: : sort out if this is a bottle neck, if there is a better way

🟡 **L456** [技术债务]: sort out if it is worth the effort to make sure this is


### venv/lib/python3.13/site-packages/networkx/conftest.py

🟡 **L102** [技术债务]: The warnings below need to be dealt with, but for now we silence them.


### venv/lib/python3.13/site-packages/cvxpy/settings.py

🟡 **L139** [技术债务]: (akshayka): These should be defined in a solver module.

🟡 **L143** [技术债务]: (akshayka): These should be defined in a solver module.


### venv/lib/python3.13/site-packages/sqlparse/keywords.py

🟡 **L41** [技术债务]: (andi): VALUES shouldn't be listed here

🟡 **L53** [技术债务]: (atronah): never match,


### venv/lib/python3.13/site-packages/sqlparse/cli.py

🟡 **L28** [技术债务]: Add CLI Tests

🟡 **L29** [技术债务]: Simplify formatter by using argparse `type` arguments


### venv/lib/python3.13/site-packages/sqlparse/sql.py

🟡 **L109** [技术债务]: Add test for regex with is_keyword = false

🟡 **L285** [技术债务]: May need to re-add default value to idx


### venv/lib/python3.13/site-packages/pure_eval/core.py

🟡 **L411** [技术债务]: exclude inner modules, e.g. numpy.random.__name__ == 'numpy.random' != 'random'

🟡 **L412** [技术债务]: exclude common module abbreviations, e.g. numpy as np, pandas as pd


### venv/lib/python3.13/site-packages/mako/lexer.py

🟡 **L268** [技术债务]: no coverage here


### venv/lib/python3.13/site-packages/mako/parsetree.py

🟡 **L204** [技术债务]: make the "filter" shortcut list configurable at parse/gen time


### venv/lib/python3.13/site-packages/mako/codegen.py

🟡 **L949** [技术债务]: we can put namespace-specific checks here, such

🟡 **L991** [技术债务]: figure out best way to specify


### venv/lib/python3.13/site-packages/mako/pygen.py

🟡 **L118** [技术债务]: no coverage here


### venv/lib/python3.13/site-packages/grpc/_channel.py

🟡 **L257** [技术债务]: (xuanwn): Create a base class for IntegratedCall and SegregatedCall.

🟡 **L1810** [技术债务]: (xuanwn): Refactor this: https://github.com/grpc/grpc/issues/31704

🟡 **L2244** [技术债务]: (https://github.com/grpc/grpc/issues/12531): Several releases


### venv/lib/python3.13/site-packages/grpc/_observability.py

🟡 **L285** [技术债务]: (xuanwn): use channel args to exclude those metrics.


### venv/lib/python3.13/site-packages/grpc/_server.py

🟡 **L1170** [技术债务]: (https://github.com/grpc/grpc/issues/6597): eliminate these fields.

🟡 **L1226** [技术债务]: (https://github.com/grpc/grpc/issues/6597): delete this function.

🟡 **L1450** [技术债务]: (xuanwn): We should validate method_handlers first.


### venv/lib/python3.13/site-packages/grpc/_auth.py

🟡 **L37** [技术债务]: (xuanwn): Give credentials an actual type.


### venv/lib/python3.13/site-packages/mpmath/ctx_mp.py

🟡 **L306** [技术债务]: add more of these, make consistent, write docstrings, ...


### venv/lib/python3.13/site-packages/mpmath/math2.py

🟡 **L207** [技术债务]: sinpi

🟡 **L221** [技术债务]: sinpi


### venv/lib/python3.13/site-packages/pyparsing/helpers.py

🟡 **L973** [技术债务]: - determine why this statement can't be included in the following


### venv/lib/python3.13/site-packages/redis/event.py

🟡 **L85** [技术债务]: Make dispatcher to accept external mappings.


### venv/lib/python3.13/site-packages/redis/connection.py

🟡 **L245** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L1378** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L1743** [技术债务]: Investigate if it's possible to unpack command

🟡 **L1810** [技术债务]: Rename this API; it detects pending data or dirty/closed


### venv/lib/python3.13/site-packages/redis/lock.py

🟡 **L259** [技术债务]: this can be simplified when the context manager is finished


### venv/lib/python3.13/site-packages/jinja2/ext.py

🟡 **L251** [技术债务]: the i18n extension is currently reevaluating values in a few


### venv/lib/python3.13/site-packages/seaborn/matrix.py

🟡 **L798** [技术债务]: We should set these to transparent instead

🟡 **L1005** [技术债务]: this code has consistently caused problems when we


### venv/lib/python3.13/site-packages/seaborn/_base.py

🟡 **L45** [技术债务]: Putting this here so we can continue to use a lot of the

🟡 **L106** [技术债务]: add generic parameters

🟡 **L273** [技术债务]: do we want to do something complicated to ensure contrast?

🟡 **L310** [技术债务]: add generic parameters

🟡 **L419** [技术债务]: this is going to cause us trouble later, because we

🟡 **L530** [技术债务]: add generic parameters

🟡 **L636** [技术债务]: Lots of tests assume that these are called to initialize the

🟡 **L777** [技术债务]: is there a safer/more generic way to ensure Series?

🟡 **L882** [技术债务]: should this default to using all (non x/y?) semantics?

🟡 **L996** [技术债务]: this should happen in some centralized location

🟡 **L1165** [技术债务]: -- Add axes labels

🟡 **L1191** [技术债务]: ax could default to None and use attached axes if present

🟡 **L1390** [技术债务]: this method could also set the grid state? Since we like to have no

🟡 **L1395** [技术债务]: if we are going to set visual properties of the axes with these methods,

🟡 **L1398** [技术债务]: another, and distinct idea, is to expose a cut= param here

🟡 **L1460** [技术债务]: we can replace this with typing.Literal on Python 3.8+


### venv/lib/python3.13/site-packages/seaborn/categorical.py

🟡 **L602** [技术债务]: rename user_kws?

🟡 **L1949** [技术债务]: how to get default color?

🟡 **L3025** [技术债务]: Uncomment when removing deprecation backcompat


### venv/lib/python3.13/site-packages/seaborn/_docstrings.py

🟡 **L62** [技术债务]: is "vector" the best term here? We mean to imply 1D data with a variety

🟡 **L65** [技术债务]: now that we can parse numpydoc style strings, do we need to define dicts

🟡 **L75** [技术债务]: add link to user guide narrative when exists


### venv/lib/python3.13/site-packages/seaborn/regression.py

🟡 **L413** [技术债务]: abstraction


### venv/lib/python3.13/site-packages/seaborn/axisgrid.py

🟡 **L435** [技术债务]: this doesn't account for axis labels

🟡 **L1474** [技术债务]: add optional density ticks (on the right)

🟡 **L2271** [技术债务]: process pair parameters for bins, etc. and pass


### venv/lib/python3.13/site-packages/seaborn/relational.py

🟡 **L194** [技术债务]: where best to define default parameters?

🟡 **L209** [技术债务]: this is messy, we want the mapping to be agnostic about

🟡 **L261** [技术债务]: abstract variable to aggregate over here-ish. Better name?

🟡 **L268** [技术债务]: How to handle NA? We don't want NA to propagate through to the

🟡 **L288** [技术债务]: eventually relax this constraint

🟡 **L341** [技术债务]: handling of orientation will need to happen here

🟡 **L389** [技术债务]: this is messy, we want the mapping to be agnostic about

🟡 **L432** [技术债务]: in more recent matplotlib (which?) can pass a MarkerStyle here


### venv/lib/python3.13/site-packages/seaborn/distributions.py

🟡 **L115** [技术债务]: this could go down to core, but putting it here now.

🟡 **L124** [技术债务]: This could also be in core, but it should have a better name.

🟡 **L132** [技术债务]: see above points about where this should go

🟡 **L140** [技术债务]: note that this doesn't handle numeric mappings like the relational plots

🟡 **L233** [技术债务]: we should have some central clearinghouse for checking if any

🟡 **L444** [技术债务]: alternatively, clip at min/max bins?

🟡 **L543** [技术债务]: make parameter?

🟡 **L886** [技术债务]: if possible, I would like to move the contour

🟡 **L958** [技术债务]: make parameter?

🟡 **L1160** [技术债务]: could add a pcolormesh based option as well

🟡 **L1195** [技术债务]: if possible, I would like to move the contour

🟡 **L1309** [技术债务]: ideally i'd like the legend artist to look like a rug

🟡 **L2250** [技术债务]: with expand_margins=True, each facet expands margins... annoying!


### venv/lib/python3.13/site-packages/seaborn/_compat.py

🟡 **L25** [技术债务]: more helpful error if this fails?


### venv/lib/python3.13/site-packages/cloudpickle/cloudpickle.py

🟡 **L1349** [技术债务]: decorrelate reducer_override (which is tied to CPython's


### venv/lib/python3.13/site-packages/fsspec/compression.py

🟡 **L14** [技术债务]: files should also be available as contexts


### venv/lib/python3.13/site-packages/fsspec/generic.py

🟡 **L328** [技术债务]: special case for one FS being local, which can use get/put

🟡 **L329** [技术债务]: special case for one being memFS, which can use cat/pipe


### venv/lib/python3.13/site-packages/fsspec/asyn.py

🟡 **L1059** [技术债务]: readahead might still be useful here, but needs async version


### venv/lib/python3.13/site-packages/fsspec/spec.py

🟡 **L549** [技术债务]: allow equivalent of -name parameter


### venv/lib/python3.13/site-packages/fsspec/caching.py

🟡 **L85** [技术债务]: use rich for better formatting

🟡 **L486** [技术债务]: only set start/end after fetch, in case it fails?


### venv/lib/python3.13/site-packages/fsspec/utils.py

🟡 **L300** [技术债务]: allow length to be None and read to the end of the file?


### venv/lib/python3.13/site-packages/markdown/core.py

🟡 **L119** [技术债务]: Maybe delete this. It does not appear to be used anymore.


### venv/lib/python3.13/site-packages/markdown/test_tools.py

🟡 **L86** [技术债务]: If/when actual output ends with a newline, then use:


### venv/lib/python3.13/site-packages/llvmlite/__init__.py

🟡 **L5** [技术债务]: Remove me once typed pointers are no longer supported.


### venv/lib/python3.13/site-packages/xgboost/sklearn.py

🟡 **L2427** [技术债务]: (jiamingy): base margin and group weight is not yet supported. We might


### venv/lib/python3.13/site-packages/xgboost/data.py

🟡 **L506** [技术债务]: (jiamingy): Is there a better way to access the arrow buffer along with

🟡 **L591** [技术债务]: (jiamingy): Investigate the possibility of using dataframe protocol or arrow


### venv/lib/python3.13/site-packages/executing/_position_node_finder.py

🟡 **L331** [技术债务]: investigate

🟡 **L678** [技术债务]: match expressions are not supported for now


### venv/lib/python3.13/site-packages/et_xmlfile/incremental_tree.py

🟡 **L752** [技术债务]: can this be handled in XML 1.0?


### venv/lib/python3.13/site-packages/jedi/parser_utils.py

🟡 **L100** [技术债务]: We have to check next leaves until there are no new

🟡 **L152** [技术债务]: this is pretty bad, we should probably just normalize.

🟡 **L194** [技术债务]: in some particular cases, the tree doesn't seem to be linked


### venv/lib/python3.13/site-packages/setup/extensions.py

🟡 **L38** [技术债务]: wheels should be compiled with openmp ...


### venv/lib/python3.13/site-packages/skopt/searchcv.py

🟡 **L506** [技术债务]: Accept callbacks via the constructor?


### venv/lib/python3.13/site-packages/fontTools/__main__.py

🟡 **L8** [技术债务]: Handle library-wide options. Eg.:

🟡 **L12** [技术债务]: Allow a way to run arbitrary modules? Useful for setting


### venv/lib/python3.13/site-packages/werkzeug/http.py

🟡 **L1381** [技术债务]: Remove encoding dance, it seems like clients accept UTF-8 keys


### venv/lib/python3.13/site-packages/sentry_sdk/tracing.py

🟡 **L208** [技术债务]: this is `maxlen - 1` only to preserve historical behavior

🟡 **L345** [技术债务]: this should really live on the Transaction class rather than the Span

🟡 **L517** [技术债务]: -neel move away from this kwargs stuff, it's confusing and opaque

🟡 **L648** [技术债务]: -neel remove in major, we keep this for backwards compatibility

🟡 **L724** [技术债务]: -neel remove redundant tag in major


### venv/lib/python3.13/site-packages/sentry_sdk/_types.py

🟡 **L255** [技术债务]: We can expand on this type

🟡 **L261** [技术债务]: We can expand on this type

🟡 **L265** [技术债务]: We can expand on this type

🟡 **L293** [技术债务]: We can expand on this type

🟡 **L296** [技术债务]: We can expand on this type

🟡 **L310** [技术债务]: Make a proper type definition for this (PRs welcome!)

🟡 **L392** [技术债务]: Make a proper type definition for this (PRs welcome!)

🟡 **L395** [技术债务]: Make a proper type definition for this (PRs welcome!)

🟡 **L398** [技术债务]: Make a proper type definition for this (PRs welcome!)


### venv/lib/python3.13/site-packages/sentry_sdk/tracing_utils.py

🟡 **L146** [技术债务]: Bring back capturing of params by default


### venv/lib/python3.13/site-packages/sentry_sdk/hub.py

🟡 **L586** [技术债务]: used to return None when client is None. Check if this changes behavior.


### venv/lib/python3.13/site-packages/sentry_sdk/api.py

🟡 **L242** [技术债务]: used to return None when client is None. Check if this changes behavior.


### venv/lib/python3.13/site-packages/sentry_sdk/scope.py

🟡 **L571** [技术债务]: -neel this below is a BIG code smell but requires a bunch of other refactoring

🟡 **L1291** [技术债务]: rename to start_span once we drop the old API

🟡 **L1760** [技术债务]: turn Logs, Metrics into actual classes


### venv/lib/python3.13/site-packages/bs4/element.py

🟡 **L1297** [技术债务]: -TYPING: "There is no syntax to indicate optional or

🟡 **L1578** [技术债务]: -TYPING This should be SupportsIndex|slice but SupportsIndex

🟡 **L2324** [技术债务]: can't reference BeautifulSoup class in this module

🟡 **L3230** [技术债务]: Using the @overload decorator to express the three ways you


### venv/lib/python3.13/site-packages/bs4/filter.py

🟡 **L220** [技术债务]: -TYPING: All MatchRule objects also have an attribute


### venv/lib/python3.13/site-packages/bs4/dammit.py

🟡 **L86** [技术债务]: -TYPING: The Pattern type here could use more refinement, but it's tricky.


### venv/lib/python3.13/site-packages/mlflow/environment_variables.py

🟡 **L76** [技术债务]: Remove this block in MLflow 3.2.0


### venv/lib/python3.13/site-packages/mlflow/__init__.py

🟡 **L268** [技术债务]: Prompt Registry APIs are moved to the `mlflow.genai` namespace and direct

🟡 **L428** [技术债务]: Prompt Registry APIs are moved to the `mlflow.genai` namespace and direct


### venv/lib/python3.13/site-packages/torch/_meta_registrations.py

🟡 **L677** [技术债务]: Ideally, we'd insert a deferred runtime assert here, but if we are

🟡 **L966** [技术债务]: should probably check that lengths and offset aren't both set, but

🟡 **L4868** [技术债务]: handle out

🟡 **L5911** [技术债务]: Deduplicate this with canonicalize_dim

🟡 **L7846** [技术债务]: Query cudnnGetRNNTrainingReserveSize (expose to python)

🟡 **L8764** [技术债务]: This logic only holds for RHS tensor in 2d-3d case.


### venv/lib/python3.13/site-packages/torch/library.py

🟡 **L338** [技术债务]: (rzou): We're gonna need to stage this change with torchvision,

🟡 **L421** [技术债务]: in future, add more info about where the existing function is registered (this info is

🟡 **L475** [技术债务]: in future, add more info about where the existing function is registered (this info is


### venv/lib/python3.13/site-packages/torch/_jit_internal.py

🟡 **L1145** [技术债务]: __name__ not set for submodules in recursive script

🟡 **L1440** [技术债务]: support future


### venv/lib/python3.13/site-packages/torch/_ops.py

🟡 **L78** [技术债务]: The cache is NOT currently used by HigherOrderOperator, but it should!

🟡 **L127** [技术债务]: (voz): Should we replace setting DispatchKey.Python entirely with setting mode keys?

🟡 **L425** [技术债务]: (rzou): we should support torch_dispatch calling convention too.

🟡 **L467** [技术债务]: (rzou): we should support torch_dispatch calling convention too.

🟡 **L950** [技术债务]: We also need to handle tensor subclasses here

🟡 **L951** [技术债务]: (voz): We should walk all the nodes here / turn it into a list, topmode is ok for now.

🟡 **L1014** [技术债务]: We could potentially have lots of debugging wrappers against

🟡 **L1048** [技术债务]: add more methods to expose information about input and output arguments

🟡 **L1057** [技术债务]: we should be calling the fallback for these, but a fallthrough is almost close

🟡 **L1237** [技术债务]: disallow access to overloads registered by JIT

🟡 **L1281** [技术债务]: use this to make a __dir__


### venv/lib/python3.13/site-packages/torch/_utils_internal.py

🟡 **L252** [技术债务]: placeholder, get actual value


### venv/lib/python3.13/site-packages/torch/__init__.py

🟡 **L624** [技术债务]: Force specialization

🟡 **L635** [技术债务]: A more relaxed guard is possible here, where you guard to

🟡 **L906** [技术债务]: Probably can make bool work too, just lazy

🟡 **L1220** [技术债务]: Call like get_device_index() method corresponding to

🟡 **L2438** [技术债务]: CUDA Graph does not work well with CUPTI teardown.


### venv/lib/python3.13/site-packages/torch/types.py

🟡 **L67** [技术债务]: refactor once python 3.9 support is dropped.


### venv/lib/python3.13/site-packages/torch/__config__.py

🟡 **L12** [技术债务]: In principle, we could provide more structured version/config


### venv/lib/python3.13/site-packages/torch/_tensor.py

🟡 **L148** [技术债务]: skipping storage copy is wrong for meta, as meta

🟡 **L201** [技术债务]: Once we decide to break serialization FC, no longer

🟡 **L274** [技术债务]: remove hasattr, it's a hack to support versions of torch that

🟡 **L387** [技术债务]: Once we decide to break serialization FC, no longer

🟡 **L502** [技术债务]: Once we decide to break serialization FC, no longer

🟡 **L511** [技术债务]: remove hasattr, it's a hack to support versions of torch that

🟡 **L641** [技术债务]: make it possible to dispatch on positions/dims

🟡 **L1151** [技术债务]: (rec): the superclass says it accepts complex here,

🟡 **L1288** [技术债务]: mypy doesn't support @property, see: https://github.com/python/mypy/issues/6185


### venv/lib/python3.13/site-packages/torch/_tensor_str.py

🟡 **L150** [技术债务]: (#146647): extend this to other dtypes without casts defined, such

🟡 **L167** [技术债务]: (#113663): also add the other float8 dtypes here after arithmetic

🟡 **L269** [技术债务]: (#146647): extend this to other dtypes without casts defined, such

🟡 **L426** [技术债务]: (albanD) This needs to be updated when more than one level is supported

🟡 **L452** [技术债务]: add an API to map real -> complex dtypes

🟡 **L608** [技术债务]: This implies that ellipses is valid syntax for allocating


### venv/lib/python3.13/site-packages/torch/functional.py

🟡 **L105** [技术债务]: Move this to C++ once the jit has better support for torch.Size.

🟡 **L1683** [技术债务]: type dim as BroadcastingList when


### venv/lib/python3.13/site-packages/torch/_guards.py

🟡 **L85** [技术债务]: consider also tracking the recompilation count

🟡 **L1383** [技术债务]: (voz): Consider a toplevel torch/_source.py


### venv/lib/python3.13/site-packages/torch/serialization.py

🟡 **L1030** [技术债务]: This feature could be added in the future

🟡 **L1034** [技术债务]: the docs say that persistent_id should only return a string

🟡 **L1062** [技术债务]: Once we decide to break serialization FC, this case

🟡 **L1101** [技术债务]: There's an issue here with FC. It might be impossible to

🟡 **L1196** [技术债务]: This feature could be added in the future

🟡 **L1200** [技术债务]: the docs say that persistent_id should only return a string

🟡 **L1207** [技术债务]: Once we decide to break serialization FC, this case

🟡 **L1755** [技术债务]: Once we decide to break serialization FC, we can

🟡 **L1766** [技术债务]: Once we decide to break serialization FC, we can

🟡 **L1832** [技术债务]: Once we decide to break serialization FC, we can

🟡 **L1852** [技术债务]: Once we decide to break serialization FC, we can

🟡 **L2137** [技术债务]: Once we decide to break serialization FC, we can


### venv/lib/python3.13/site-packages/torch/_utils.py

🟡 **L193** [技术债务]: Once we decide to break serialization FC, `storage` no longer needs to

🟡 **L316** [技术债务]: Validation currently involves an expensive traversal

🟡 **L438** [技术债务]: Once we decide to break serialization FC, `storage` no longer needs to


### venv/lib/python3.13/site-packages/gunicorn/config.py

🟡 **L2684** [技术债务]: refactor all of this subclassing stdlib argparse


### venv/lib/python3.13/site-packages/gunicorn/__main__.py

🟡 **L9** [技术债务]: let runpy.run_module take care of argv[0] rewriting


### venv/lib/python3.13/site-packages/numpy/conftest.py

🟡 **L105** [技术债务]: when yield tests are gone.


### venv/lib/python3.13/site-packages/numpy/__init__.py

🟡 **L533** [技术债务]: Remove the environment variable entirely now that it is "weak"


### venv/lib/python3.13/site-packages/pandas_ta/maps.py

🟡 **L14** [技术债务]: find a dynamic solution later.


### venv/lib/python3.13/site-packages/osqp/interface.py

🟡 **L331** [技术债务]: sanity-check on types/dimensions

🟡 **L400** [技术债务]: sanity checks on types/dimensions

🟡 **L423** [技术债务]: The following structure is only to maintain backward compatibility, where x/y are attributes


### venv/lib/python3.13/site-packages/PIL/MpoImagePlugin.py

🟡 **L129** [技术债务]: hack


### venv/lib/python3.13/site-packages/PIL/PcxImagePlugin.py

🟡 **L96** [技术债务]: hey, this doesn't work with the incremental loader !!!


### venv/lib/python3.13/site-packages/PIL/ImageFile.py

🟡 **L363** [技术债务]: This is a hack to handle TIFF's JpegTables tag.

🟡 **L657** [技术债务]: make MAXBLOCK a configuration parameter


### venv/lib/python3.13/site-packages/PIL/SpiderImagePlugin.py

🟡 **L162** [技术债务]: hack


### venv/lib/python3.13/site-packages/PIL/PixarImagePlugin.py

🟡 **L61** [技术债务]: to be continued...


### venv/lib/python3.13/site-packages/PIL/MspImagePlugin.py

🟡 **L184** [技术债务]: is this the right field?


### venv/lib/python3.13/site-packages/PIL/GifImagePlugin.py

🟡 **L124** [技术债务]: hack


### venv/lib/python3.13/site-packages/PIL/ImageQt.py

🟡 **L139** [技术债务]: - is this really the best way to do this?


### venv/lib/python3.13/site-packages/PIL/PdfParser.py

🟡 **L626** [技术债务]: support reuse of deleted objects


### venv/lib/python3.13/site-packages/PIL/ImageCms.py

🟡 **L1071** [技术债务]: I get different results for the same data w. different


### venv/lib/python3.13/site-packages/PIL/PSDraw.py

🟡 **L44** [技术债务]: incomplete


### venv/lib/python3.13/site-packages/PIL/ImageDraw2.py

🟡 **L55** [技术债务]: add support for bitmap fonts


### venv/lib/python3.13/site-packages/PIL/ImageDraw.py

🟡 **L125** [技术债务]: should add a font repository


### venv/lib/python3.13/site-packages/PIL/IcoImagePlugin.py

🟡 **L89** [技术债务]: invent a more convenient method for proportional scalings


### venv/lib/python3.13/site-packages/PIL/ImageOps.py

🟡 **L57** [技术债务]: apply to lookup table, not image data


### venv/lib/python3.13/site-packages/PIL/PdfImagePlugin.py

🟡 **L57** [技术债务]: Should replace ASCIIHexDecode with RunLengthDecode


### venv/lib/python3.13/site-packages/PIL/TiffTags.py

🟡 **L214** [技术债务]: add more tags here


### venv/lib/python3.13/site-packages/PIL/TiffImagePlugin.py

🟡 **L962** [技术债务]: What about tagdata?


### venv/lib/python3.13/site-packages/PIL/ImagePalette.py

🟡 **L264** [技术债务]: supports GIMP gradients only


### venv/lib/python3.13/site-packages/PIL/McIdasImagePlugin.py

🟡 **L55** [技术债务]: add memory map support


### venv/lib/python3.13/site-packages/PIL/Image.py

🟡 **L634** [技术债务]: take "new" parameters / other image?

🟡 **L1904** [技术债务]: use self.size here?

🟡 **L2040** [技术债务]: _imaging returns a confusing error message for this case

🟡 **L2915** [技术债务]: the different transform methods need further explanation


### venv/lib/python3.13/site-packages/PIL/XVThumbImagePlugin.py

🟡 **L17** [技术债务]: make save work (this requires quantization support)


### venv/lib/python3.13/site-packages/PIL/ImImagePlugin.py

🟡 **L153** [技术债务]: this may read whole file if not a text file

🟡 **L250** [技术债务]: hack


### venv/lib/python3.13/site-packages/PIL/PsdImagePlugin.py

🟡 **L40** [技术债务]: multilayer


### venv/lib/python3.13/site-packages/PIL/JpegImagePlugin.py

🟡 **L112** [技术债务]: value will change

🟡 **L244** [技术债务]: The quantization tables can be used to estimate the

🟡 **L795** [技术债务]: issue a warning if the wrong form is used (post-1.1.7)


### venv/lib/python3.13/site-packages/PIL/ImageFont.py

🟡 **L19** [技术债务]: :

🟡 **L79** [技术债务]: add support for pilfont2 format (see FontFile.py)

🟡 **L163** [技术债务]: should be a dictionary

🟡 **L253** [技术债务]: use service provider instead


### venv/lib/python3.13/site-packages/requests/_types.py

🟡 **L55** [技术债务]: move to collections.abc when Python >= 3.12

🟡 **L56** [技术债务]: move to typing when Python >= 3.13


### venv/lib/python3.13/site-packages/requests/hooks.py

🟡 **L29** [技术债务]: response is the only one


### venv/lib/python3.13/site-packages/requests/models.py

🟡 **L1012** [技术债务]: remove cast after iter_lines rewrite


### venv/lib/python3.13/site-packages/requests/adapters.py

🟡 **L715** [技术债务]: Remove this in 3.0.0: see #2811


### venv/lib/python3.13/site-packages/html5lib/serializer.py

🟡 **L302** [技术债务]: Add namespace support here


### venv/lib/python3.13/site-packages/multidict/_compat.py

🟡 **L14** [技术债务]: Refactor for coverage. See #837.


### venv/lib/python3.13/site-packages/sklearn/conftest.py

🟡 **L210** [技术债务]: configure numpy to output scalar arrays as regular Python scalars


### venv/lib/python3.13/site-packages/sklearn/multiclass.py

🟡 **L1209** [技术债务]: there are more elaborate methods than generating the codebook


### venv/lib/python3.13/site-packages/sklearn/isotonic.py

🟡 **L162** [技术债务]: remove this branch when Scipy 1.12 is the minimum supported version


### venv/lib/python3.13/site-packages/sklearn/multioutput.py

🟡 **L755** [技术债务]: remove this condition check when the minimum supported scipy version


### venv/lib/python3.13/site-packages/sklearn/pipeline.py

🟡 **L1577** [技术债务]: merge with _fit_transform_one when all callers support callbacks

🟡 **L1960** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.

🟡 **L2009** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.

🟡 **L2083** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.


### venv/lib/python3.13/site-packages/sklearn/discriminant_analysis.py

🟡 **L122** [技术债务]: Explore the choice of using bincount + add.at as it seems sub optimal


### venv/lib/python3.13/site-packages/sklearn/calibration.py

🟡 **L927** [技术债务]: Remove casting to np.float64 when minimum supported SciPy is 1.11.2

🟡 **L989** [技术债务]: simplify once upstream issue is addressed

🟡 **L1141** [技术债务]: numpy 2.0


### venv/lib/python3.13/site-packages/flask_limiter/_limits.py

🟡 **L275** [技术债务]: if use as a context manager becomes interesting/valuable


### venv/lib/python3.13/site-packages/pyasn1_modules/rfc2985.py

🟡 **L86** [技术债务]: :

🟡 **L269** [技术债务]: Once PKCS15Token can be imported, this can be included

🟡 **L543** [技术债务]: Once PKCS15Token can be imported, this can be included


### venv/lib/python3.13/site-packages/joblib/memory.py

🟡 **L44** [技术债务]: The following object should have a data store object as a sub

🟡 **L53** [技术债务]: Same remark for the logger, and probably use the Python logging

🟡 **L583** [技术债务]: (pierreglaser): do the same with get_func_name?


### venv/lib/python3.13/site-packages/joblib/func_inspect.py

🟡 **L168** [技术债务]: Maybe add a warning here?


### venv/lib/python3.13/site-packages/joblib/logger.py

🟡 **L144** [技术债务]: Too much logic duplicated


### venv/lib/python3.13/site-packages/joblib/_store_backends.py

🟡 **L216** [技术债务]: (1.5) turn into error


### venv/lib/python3.13/site-packages/joblib/_memmapping_reducer.py

🟡 **L164** [技术债务]: check scipy sparse datastructure if scipy is installed


### venv/lib/python3.13/site-packages/joblib/parallel.py

🟡 **L2054** [技术债务]: this iterator should be batch_size * n_jobs


### venv/lib/python3.13/site-packages/prompt_toolkit/renderer.py

🟡 **L357** [技术债务]: Move following state flags into `Vt100_Output`, similar to


### venv/lib/python3.13/site-packages/pexpect/spawnbase.py

🟡 **L469** [技术债务]: self.before should be ''. Should I assert this?


### venv/lib/python3.13/site-packages/pexpect/pxssh.py

🟡 **L253** [技术债务]: This is getting messy and I'm pretty sure this isn't perfect.

🟡 **L254** [技术债务]: I need to draw a flow chart for this.

🟡 **L255** [技术债务]: Unit tests for SSH tunnels, remote SSH command exec, disabling original prompt sync

🟡 **L432** [技术债务]: May NOT be OK if expect() got tricked and matched a false prompt.


### venv/lib/python3.13/site-packages/pexpect/pty_spawn.py

🟡 **L492** [技术债务]: So does this mean Irix systems are forced to always have

🟡 **L493** [技术债务]: a 2 second delay when calling read_nonblocking? That sucks.


### venv/lib/python3.13/site-packages/xlrd/formula.py

🟡 **L1642** [技术债务]: #### if funcx == 255: # call add-in function


### venv/lib/python3.13/site-packages/xlrd/formatting.py

🟡 **L366** [技术债务]: ... a lot of work to tailor these to the user's locale.

🟡 **L470** [技术债务]: Find where formats are interpreted in Gnumeric

🟡 **L471** [技术债务]: '[h]\\ \\h\\o\\u\\r\\s' ([h] means don't care about hours > 23)


### venv/lib/python3.13/site-packages/narwhals/_utils.py

🟡 **L1690** [技术债务]: @dangotbanned: Extend with runtime behavior for `v1.*`


### venv/lib/python3.13/site-packages/tqdm/std.py

🟡 **L1450** [技术债务]: private method


### venv/lib/python3.13/site-packages/tqdm/__init__.py

🟡 **L3** [技术债务]: remove in v5.0.0

🟡 **L4** [技术债务]: remove in v5.0.0

🟡 **L5** [技术债务]: remove in v5.0.0


### venv/lib/python3.13/site-packages/tqdm/rich.py

🟡 **L77** [技术债务]: @classmethod: write()?


### venv/lib/python3.13/site-packages/tqdm/tk.py

🟡 **L31** [技术债务]: @classmethod: write()?


### venv/lib/python3.13/site-packages/tqdm/cli.py

🟡 **L117** [技术债务]: add custom support for some of the following?


### venv/lib/python3.13/site-packages/tqdm/utils.py

🟡 **L9** [技术债务]: consider using wcswidth third-party package for 0-width characters


### venv/lib/python3.13/site-packages/tqdm/gui.py

🟡 **L26** [技术债务]: @classmethod: write() on GUI?


### venv/lib/python3.13/site-packages/fastapi/encoders.py

🟡 **L58** [技术债务]: pv2 should this return strings instead?


### venv/lib/python3.13/site-packages/fastapi/routing.py

🟡 **L1227** [技术债务]: Replace or deprecate this no-scope hook so included-route

🟡 **L2212** [技术债务]: probably move this out of the Route / Route Group, same in APIRoute


### venv/lib/python3.13/site-packages/curl_cffi/curl.py

🟡 **L288** [技术债务]: use CURL_ERROR_SIZE


### venv/lib/python3.13/site-packages/tensorboard/program.py

🟡 **L281** [技术债务]: (#2801): Make `--version` a flag on only the base parser, not `serve`.

🟡 **L286** [技术债务]: (@wchargin): Convert `inspect` to a normal subcommand?


### venv/lib/python3.13/site-packages/tensorboard/manager.py

🟡 **L506** [技术债务]: (@wchargin): Check here that the provided port is still live.


### venv/lib/python3.13/site-packages/tabulate/__init__.py

🟡 **L774** [技术债务]: Add multiline support for the remaining table formats:

🟡 **L1245** [技术债务]: refactor column alignment in single-line and multiline modes


### venv/lib/python3.13/site-packages/matplotlib/backend_bases.py

🟡 **L588** [技术债务]: handle properties


### venv/lib/python3.13/site-packages/matplotlib/colorbar.py

🟡 **L787** [技术债务]: Make colorbar lines auto-follow changes in contour lines.


### venv/lib/python3.13/site-packages/matplotlib/cbook.py

🟡 **L1824** [技术债务]: do the finite filtering on this


### venv/lib/python3.13/site-packages/matplotlib/font_manager.py

🟡 **L1705** [技术债务]: _load_fontmanager should really be (used by) a method


### venv/lib/python3.13/site-packages/matplotlib/cm.py

🟡 **L21** [技术债务]: make this warn on access


### venv/lib/python3.13/site-packages/matplotlib/figure.py

🟡 **L2758** [技术债务]: I'd like to dynamically add the _repr_html_ method


### venv/lib/python3.13/site-packages/matplotlib/_mathtext.py

🟡 **L375** [技术债务]: Not sure this is guaranteed.

🟡 **L2362** [技术债务]: this should be read from the font file


### venv/lib/python3.13/site-packages/matplotlib/offsetbox.py

🟡 **L235** [技术债务]: deal with this better

🟡 **L1500** [技术债务]: Rotation needs to be accounted.


### venv/lib/python3.13/site-packages/matplotlib/widgets.py

🟡 **L1343** [技术债务]: This may need an update when switching out the canvas.

🟡 **L1874** [技术债务]: This may need an update when switching out the canvas.

🟡 **L2085** [技术债务]: make dynamic

🟡 **L2230** [技术债务]: make dynamic

🟡 **L3510** [技术债务]: set to a rotate cursor if possible?

🟡 **L3515** [技术债务]: set to a resize cursor if possible?

🟡 **L4411** [技术债务]: Make dynamic


### venv/lib/python3.13/site-packages/matplotlib/dviread.py

🟡 **L566** [技术债务]: actually read the postamble and finale?


### venv/lib/python3.13/site-packages/matplotlib/animation.py

🟡 **L282** [技术债务]: MovieWriter is still an abstract class and needs to be

🟡 **L1103** [技术债务]: Right now, after closing the figure, saving a movie won't work

🟡 **L1127** [技术债务]: Currently only FuncAnimation has a save_count

🟡 **L1137** [技术债务]: See if turning off blit is really necessary


### venv/lib/python3.13/site-packages/matplotlib/patches.py

🟡 **L4645** [技术债务]: dpi_cor is for the dpi-dependency of the linewidth.  There


### venv/lib/python3.13/site-packages/matplotlib/collections.py

🟡 **L320** [技术债务]: check to ensure that this does not fail for

🟡 **L1278** [技术债务]: check whether we can switch to


### venv/lib/python3.13/site-packages/matplotlib/spines.py

🟡 **L601** [技术债务]: Do we want to deprecate adding spines?

🟡 **L605** [技术债务]: Do we want to deprecate deleting spines?


### venv/lib/python3.13/site-packages/matplotlib/text.py

🟡 **L441** [技术债务]: This is a temporary internal method call (for _backend_pdf_ps to

🟡 **L2183** [技术债务]: : Rotation needs to be accounted.


### venv/lib/python3.13/site-packages/matplotlib/table.py

🟡 **L441** [技术债务]: Return index of the cell containing the cursor so that the user


### venv/lib/python3.13/site-packages/matplotlib/pyplot.py

🟡 **L1707** [技术债务]: numpy/numpy#24738


### venv/lib/python3.13/site-packages/matplotlib/_type1font.py

🟡 **L869** [技术债务]: and done include strings (glyph names)


### venv/lib/python3.13/site-packages/matplotlib/ticker.py

🟡 **L3082** [技术债务]: Figure out a way to still be able to display minor ticks with less


### venv/lib/python3.13/site-packages/matplotlib/image.py

🟡 **L480** [技术债务]: slice input array first

🟡 **L646** [技术债务]: make sure this is consistent with patch and patch

🟡 **L648** [技术债务]: consider returning image coordinates (shouldn't


### venv/lib/python3.13/site-packages/matplotlib/colors.py

🟡 **L1389** [技术债务]: It's a separate discussion whether we need this property on


### venv/lib/python3.13/site-packages/yaml/scanner.py

🟡 **L187** [技术债务]: support for BOM within a stream.

🟡 **L761** [技术债务]: We need to make tab handling rules more sane. A good rule is


### venv/lib/python3.13/site-packages/prometheus_client/metrics_core.py

🟡 **L330** [技术债务]: Handle None gsum_value correctly. Currently a None will fail exposition but is allowed here.


### venv/lib/python3.13/site-packages/pythonjsonlogger/core.py

🟡 **L196** [技术债务]: Validate comma format

🟡 **L243** [技术债务]: logging.LogRecord.msg and logging.LogRecord.message in typeshed


### venv/lib/python3.13/site-packages/torchgen/native_function_generation.py

🟡 **L486** [技术债务]: Remove this after figuring out CI job failures related to min, max, mean


### venv/lib/python3.13/site-packages/torchgen/gen.py

🟡 **L391** [技术债务]: for ops with structured_delegate it should check the dispatch table of

🟡 **L834** [技术债务]: This was historically used to help some JIT interop code

🟡 **L1095** [技术债务]: Get rid of dynamic_type, after getting tools/autograd

🟡 **L1362** [技术债务]: What exactly is the semantics of the 'dispatch' field?

🟡 **L1486** [技术债务]: how come ValuesView isn't a Sequence lol

🟡 **L2290** [技术债务]: this condition is a bit questionable

🟡 **L2919** [技术债务]: stop generating CUDA kernels for non-CUDA builds


### venv/lib/python3.13/site-packages/torchgen/gen_functionalization_type.py

🟡 **L1194** [技术债务]: The below ops all have "problematic" schemas that prevent them from


### venv/lib/python3.13/site-packages/torchgen/gen_aoti_c_shim.py

🟡 **L43** [技术债务]: how about other floating point types?


### venv/lib/python3.13/site-packages/torchgen/model.py

🟡 **L534** [技术债务]: figure out what this does

🟡 **L771** [技术债务]: verify that the tag is valid and has an entry in tags.yaml

🟡 **L860** [技术债务]: maybe it's better to test the return

🟡 **L1035** [技术债务]: probably better to accumulate these errors and report them all

🟡 **L1455** [技术债务]: This discrepancy isn't required; we could also generated

🟡 **L1521** [技术债务]: Need to handle collisions with argument names at some point

🟡 **L2211** [技术债务]: deduplicate annotation matching with Return

🟡 **L2508** [技术债务]: Use a real parser here; this will get bamboozled

🟡 **L2634** [技术债务]: These invariants are weirdly asymmetric?

🟡 **L2635** [技术债务]: Fancier types?


### venv/lib/python3.13/site-packages/torchgen/utils.py

🟡 **L55** [技术债务]: Use a real parser here; this will get bamboozled

🟡 **L93** [技术债务]: this does the wrong thing with KeyError


### venv/lib/python3.13/site-packages/torchgen/gen_backend_stubs.py

🟡 **L155** [技术债务]: allow structured external backends later.


### venv/lib/python3.13/site-packages/pydantic_settings/utils.py

🟡 **L41** [技术债务]: remove and replace usage by `isinstance(cls, type) and issubclass(cls, class_or_tuple)`


### venv/lib/python3.13/site-packages/urllib3/_base_connection.py

🟡 **L22** [技术债务]: Remove this in favor of a better


### venv/lib/python3.13/site-packages/urllib3/response.py

🟡 **L908** [技术债务]: Ideally we'd like to include the url in the ReadTimeoutError but

🟡 **L1152** [技术债务]: make sure to initially read enough data to get past the headers

🟡 **L1217** [技术债务]: , this method's type doesn't say returning None is possible

🟡 **L1395** [技术债务]: Rewrite this method and make it a class with a better structured logic.


### venv/lib/python3.13/site-packages/urllib3/exceptions.py

🟡 **L306** [技术债务]: (t-8ch): Stop inheriting from AssertionError in v2.0.


### venv/lib/python3.13/site-packages/urllib3/connectionpool.py

🟡 **L578** [技术债务]: Add optional support for socket.gethostbyname checking.

🟡 **L1108** [技术债务]: revise this, see https://github.com/urllib3/urllib3/issues/2791


### venv/lib/python3.13/site-packages/blinker/base.py

🟡 **L135** [技术债务]: no explanation or test for this

🟡 **L336** [技术债务]: test receivers_for(ANY)


### venv/lib/python3.13/site-packages/lightgbm/basic.py

🟡 **L1124** [技术债务]: remove 'type: ignore[assignment]' when https://github.com/lightgbm-org/LightGBM/pull/6348 is resolved.

🟡 **L1132** [技术债务]: remove 'type: ignore[assignment]' when https://github.com/lightgbm-org/LightGBM/pull/6348 is resolved.

🟡 **L1170** [技术债务]: remove 'type: ignore[assignment]' when https://github.com/lightgbm-org/LightGBM/pull/6348 is resolved.


### venv/lib/python3.13/site-packages/asttokens/asttokens.py

🟡 **L177** [技术债务]: add test for multibyte unicode. We need to translate offsets from ast module (which


### venv/lib/python3.13/site-packages/setuptools/_normalization.py

🟡 **L151** [技术债务]: Replace with only safe_version in the future (no need for best effort)


### venv/lib/python3.13/site-packages/setuptools/_static.py

🟡 **L24** [技术债务]: Remove after deprecation warning is solved


### venv/lib/python3.13/site-packages/setuptools/_core_metadata.py

🟡 **L122** [技术债务]: Replace with `raise ValueError("newlines not allowed")`


### venv/lib/python3.13/site-packages/setuptools/unicode_utils.py

🟡 **L113** [技术债务]: Add a deadline?


### venv/lib/python3.13/site-packages/setuptools/dist.py

🟡 **L129** [技术债务]: define due_date, it may break old packages that are no longer

🟡 **L174** [技术债务]: should there be a `due_date` here?

🟡 **L443** [技术债务]: Should we add a due date? It may affect old/unmaintained

🟡 **L545** [技术债务]: 'Distribution._parse_config_files' is too complex (14)

🟡 **L688** [技术债务]: 'Distribution._set_command_options' is too complex (14)


### venv/lib/python3.13/site-packages/psycopg2/tz.py

🟡 **L158** [技术债务]: pre-generate some interesting time zones?


### venv/lib/python3.13/site-packages/psycopg2/_range.py

🟡 **L526** [技术债务]: probably won't work with infs, nans and other tricky cases.


### venv/lib/python3.13/site-packages/eventlet/queue.py

🟡 **L390** [技术债务]: (stephenfin): Remove conditional when we bump the minimum Python


### venv/lib/python3.13/site-packages/eventlet/tpool.py

🟡 **L58** [技术债务]: this is probably redundant since using sockets instead of pipe now


### venv/lib/python3.13/site-packages/eventlet/db_pool.py

🟡 **L312** [技术债务]: remove repetition; options to consider:


### venv/lib/python3.13/site-packages/eventlet/wsgi.py

🟡 **L112** [技术债务]: maybe log a warning if self.hundred_continue_headers


### venv/lib/python3.13/site-packages/itsdangerous/timed.py

🟡 **L182** [技术债务]: Signature is incompatible because parameters were added


### venv/lib/python3.13/site-packages/parso/cache.py

🟡 **L238** [技术债务]: Maybe log this?


### venv/lib/python3.13/site-packages/pydantic/functional_validators.py

🟡 **L217** [技术债务]: if `schema['serialization']` is one of `'include-exclude-dict/sequence',

🟡 **L879** [技术债务]: make use of PEP 747


### venv/lib/python3.13/site-packages/pydantic/alias_generators.py

🟡 **L7** [技术债务]: in V3, change the argument names to be more descriptive


### venv/lib/python3.13/site-packages/pydantic/fields.py

🟡 **L53** [技术债务]: PEP 747: use TypeForm:

🟡 **L99** [技术债务]: PEP 747: use TypeForm:

🟡 **L151** [技术债务]: PEP 747: use TypeForm:

🟡 **L361** [技术债务]: check for classvar and error?

🟡 **L422** [技术债务]: check for classvar and error?

🟡 **L424** [技术债务]: infer from the default, this can be done in v3 once we treat final fields with

🟡 **L840** [技术债务]: properly make use of the protocol (https://rich.readthedocs.io/en/stable/pretty.html#rich-repr-protocol)

🟡 **L926** [技术债务]: use `_typing_extra.EllipsisType` when we drop Py3.9


### venv/lib/python3.13/site-packages/pydantic/mypy.py

🟡 **L548** [技术债务]: Only do this if the first argument of the decorated function is `cls`

🟡 **L657** [技术债务]: We shouldn't be performing type operations during the main


### venv/lib/python3.13/site-packages/pydantic/json_schema.py

🟡 **L527** [技术债务]: I dislike that we have to wrap these basic dict updates in callables, is there any way around this?

🟡 **L775** [技术债务]: should we add regex flags to the pattern?

🟡 **L1433** [技术债务]: Need to read the default value off of model config or whatever

🟡 **L1434** [技术债务]: replace this default False


### venv/lib/python3.13/site-packages/pydantic/type_adapter.py

🟡 **L291** [技术债务]: we don't go through the rebuild logic here directly because we don't want


### venv/lib/python3.13/site-packages/pydantic/functional_serializers.py

🟡 **L237** [技术债务]: PEP 747 (grep for 'return_type' on the whole code base):


### venv/lib/python3.13/site-packages/pydantic/dataclasses.py

🟡 **L307** [技术债务]: `parent_namespace` is currently None, but we could do the same thing as Pydantic models:


### venv/lib/python3.13/site-packages/pydantic/main.py

🟡 **L1094** [技术债务]: - matching error

🟡 **L1746** [技术债务]: PEP 747: replace `Any` by the TypeForm:


### venv/lib/python3.13/site-packages/polars/__init__.py

🟡 **L60** [技术债务]: remove need for importing wrap utils at top level


### venv/lib/python3.13/site-packages/polars/selectors.py

🟡 **L109** [技术债务]: Don't use this as it collects a schema (can be very expensive for LazyFrame).

🟡 **L190** [技术债务]: Don't use this as it collects a schema (can be very expensive for LazyFrame).

🟡 **L2035** [技术债务]: allow explicit selection by scale/precision?


### venv/lib/python3.13/site-packages/iniconfig/__init__.py

🟡 **L64** [技术债务]: investigate possible mypy bug wrt matching the passed over data


### venv/lib/python3.13/site-packages/typing_inspection/introspection.py

🟡 **L221** [技术债务]: at some point, we could switch to an enum flag, so that multiple sources

🟡 **L224** [技术债务]: if/when https://peps.python.org/pep-0767/ is accepted, add 'read_only'

🟡 **L319** [技术债务]: use a match statement when Python 3.9 support is dropped.


### venv/lib/python3.13/site-packages/psutil/_pswindows.py

🟡 **L794** [技术债务]: the C ext can probably be refactored in order


### venv/lib/python3.13/site-packages/psutil/_psaix.py

🟡 **L50** [技术债务]: what status is this?

🟡 **L155** [技术债务]: - the filtering logic should be better checked so that

🟡 **L222** [技术债务]: rewrite this in C (entstat forks, so use truss -f to follow.

🟡 **L496** [技术债务]: rewrite without using procfiles (stat /proc/pid/fd/* and then


### venv/lib/python3.13/site-packages/psutil/_pssunos.py

🟡 **L197** [技术债务]: - the filtering logic should be better checked so that

🟡 **L244** [技术债务]: refactor and use _common.conn_to_ntuple.

🟡 **L591** [技术债务]: rewrite this in C (...but the damn netstat source code


### venv/lib/python3.13/site-packages/traitlets/traitlets.py

🟡 **L1413** [技术债务]: raise if cloning locked!

🟡 **L1501** [技术债务]: Separate in a rollback function per notification type.


### venv/lib/python3.13/site-packages/dependency_injector/schema.py

🟡 **L88** [技术债务]: refactoring

🟡 **L129** [技术债务]: refactoring


### venv/lib/python3.13/site-packages/lxml/_elementpath.py

🟡 **L140** [技术债务]: replace with real parser!!! refs:

🟡 **L228** [技术债务]: what if the selector is "*" ?


### venv/lib/python3.13/site-packages/lxml/doctestcompare.py

🟡 **L268** [技术债务]: probably PIs should be handled specially too?

🟡 **L278** [技术债务]: probably PIs should be handled specially too?


### venv/lib/python3.13/site-packages/scipy/conftest.py

🟡 **L580** [技术债务]: populate the dict once


### venv/lib/python3.13/site-packages/coverage/sysmon.py

🟡 **L196** [技术债务]: should_start_context and switch_context are unused!

🟡 **L202** [技术债务]: warn is unused.


### venv/lib/python3.13/site-packages/coverage/parser.py

🟡 **L620** [技术债务]: Shouldn't the cause messages join with "and" instead of "or"?


### venv/lib/python3.13/site-packages/yarl/_url.py

🟡 **L701** [技术债务]: add a keyword-only option for keeping user/pass maybe?


### venv/lib/python3.13/site-packages/gitdb/pack.py

🟡 **L539** [技术债务]: figure out whether we should better keep the lock, or maybe

🟡 **L679** [技术债务]: make this a simple sorted offset array which can be bisected


### venv/lib/python3.13/site-packages/gitdb/fun.py

🟡 **L371** [技术债务]: Use a deque here, and decide by the index whether to extend


### venv/lib/python3.13/site-packages/gitdb/stream.py

🟡 **L406** [技术债务]: There should be a special case if there is only one stream


### venv/lib/python3.13/site-packages/croniter/croniter.py

🟡 **L209** [技术债务]: Check negative DST

🟡 **L228** [技术债务]: Check negative DST


### venv/lib/python3.13/site-packages/git/cmd.py

🟡 **L202** [技术债务]: Why join? Will block if stdin needs feeding...

🟡 **L385** [技术债务]: Bad choice to mimic `proc.wait()` but with different args.


### venv/lib/python3.13/site-packages/git/config.py

🟡 **L523** [技术债务]: Handle other quoted content, especially well-formed backslash escapes.

🟡 **L653** [技术债务]: Replace cast with assert to narrow type, once sure.

🟡 **L770** [技术债务]: Use PathLike (having dropped 3.5).

🟡 **L800** [技术债务]: Figure out if default or return type can really include bool.


### venv/lib/python3.13/site-packages/git/util.py

🟡 **L558** [技术债务]: when py3.7 support is dropped, use the new interpolation f"{variable=}"

🟡 **L576** [技术债务]: No close proc-streams??


### venv/lib/python3.13/site-packages/git/__init__.py

🟡 **L196** [技术债务]: If __version__ is made dynamic and lazily fetched, put that case right here.


### venv/lib/python3.13/site-packages/git/diff.py

🟡 **L616** [技术债务]: Here SLURPING raw, need to re-phrase header-regexes linewise.


### venv/lib/python3.13/site-packages/pandas/_typing.py

🟡 **L386** [技术债务]: (typing#684): add Ellipsis, see


### venv/lib/python3.13/site-packages/dateutil/rrule.py

🟡 **L1182** [技术债务]: Check -numweeks for next year.


### venv/lib/python3.13/site-packages/_pytest/compat.py

🟡 **L127** [技术债务]: (RonnyPfannschmidt): This function should be refactored when we


### venv/lib/python3.13/site-packages/_pytest/terminal.py

🟡 **L113** [技术债务]: Deprecate config.quiet


### venv/lib/python3.13/site-packages/_pytest/junitxml.py

🟡 **L510** [技术债务]: breaks for --dist=each


### venv/lib/python3.13/site-packages/_pytest/python.py

🟡 **L1568** [技术债务]: If escaping is turned off and the user passes bytes,

🟡 **L1640** [技术债务]: this is a hell of a hack

🟡 **L1657** [技术债务]: determine sound type limitations

🟡 **L1741** [技术债务]: Type ignored -- breaks Liskov Substitution.


### venv/lib/python3.13/site-packages/_pytest/reports.py

🟡 **L523** [技术债务]: Check if this is actually reachable.

🟡 **L575** [技术债务]: Investigate whether the duck typing is really necessary here.


### venv/lib/python3.13/site-packages/_pytest/doctest.py

🟡 **L316** [技术债务]: Type ignored -- breaks Liskov Substitution.

🟡 **L346** [技术债务]: ReprFileLocation doesn't expect a None lineno.


### venv/lib/python3.13/site-packages/_pytest/raises.py

🟡 **L477** [技术债务]: harmonize with ExceptionInfo.match

🟡 **L687** [技术债务]: move common code into superclass


### venv/lib/python3.13/site-packages/_pytest/nodes.py

🟡 **L506** [技术债务]: This omits the style= parameter which breaks Liskov Substitution.


### venv/lib/python3.13/site-packages/_pytest/main.py

🟡 **L1005** [技术债务]: Remove the hacky split once the collection structure


### venv/lib/python3.13/site-packages/_pytest/legacypath.py

🟡 **L389** [技术债务]: This assert is probably not valid in all cases.


### venv/lib/python3.13/site-packages/_pytest/fixtures.py

🟡 **L716** [技术债务]: (pytest10.1): Remove the `warn` and `if` and call

🟡 **L1385** [技术债务]: paramspec/return type annotation tracking and storing


### venv/lib/python3.13/site-packages/_pytest/cacheprovider.py

🟡 **L580** [技术债务]: evaluate generating upward relative paths


### venv/lib/python3.13/site-packages/pyarrow/util.py

🟡 **L248** [技术债务]: (GH-48593): Remove when libc++ supports std::chrono timezone


### venv/lib/python3.13/site-packages/pyarrow/cffi.py

🟡 **L79** [技术债务]: use out-of-line mode for faster import and avoid C parsing


### venv/lib/python3.13/site-packages/pyarrow/__init__.py

🟡 **L293** [技术债务]: Deprecate these somehow in the pyarrow namespace

🟡 **L424** [技术债务]: (wesm): Is this necessary, or does setuptools within a conda


### venv/lib/python3.13/site-packages/pyarrow/feather.py

🟡 **L115** [技术债务]: (wesm): Not sure when else this might be reached


### venv/lib/python3.13/site-packages/pyarrow/fs.py

🟡 **L402** [技术债务]: can we read/pass metadata (e.g. Content-Type) in the methods below?


### venv/lib/python3.13/site-packages/prettytable/colortable.py

🟡 **L114** [技术债务]: Validate option


### venv/lib/python3.13/site-packages/gymnasium/wrappers/array_conversion.py

🟡 **L50** [技术债务]: Switch to ArrayAPI type once https://github.com/data-apis/array-api/pull/589 is merged

🟡 **L51** [技术债务]: Switch to ArrayAPI type if available


### venv/lib/python3.13/site-packages/gymnasium/utils/env_checker.py

🟡 **L338** [技术债务]: - Add to gymlibrary.ml?


### venv/lib/python3.13/site-packages/gymnasium/wrappers/vector/vectorize_action.py

🟡 **L86** [技术债务]: We could compute single_action_space from the action_space if only the latter is provided and avoid the warning below.


### venv/lib/python3.13/site-packages/gymnasium/wrappers/vector/vectorize_observation.py

🟡 **L83** [技术债务]: We could compute single_observation_space from the observation_space if only the latter is provided and avoid the warning below.


### venv/lib/python3.13/site-packages/finrl/agents/stablebaselines3/hyperparams_opt.py

🟡 **L53** [技术债务]: account when using multiple envs

🟡 **L136** [技术债务]: account when using multiple envs


### venv/lib/python3.13/site-packages/pyasn1/type/constraint.py

🟡 **L747** [技术债务]: :


### venv/lib/python3.13/site-packages/pyasn1/type/univ.py

🟡 **L1735** [技术债务]: remove when Py2.5 support is gone

🟡 **L1963** [技术债务]: we should wrap componentType with UnnamedType to carry


### venv/lib/python3.13/site-packages/pyasn1/codec/der/decoder.py

🟡 **L23** [技术债务]: prohibit non-canonical encoding


### venv/lib/python3.13/site-packages/pyasn1/codec/der/encoder.py

🟡 **L34** [技术债务]: move out of sorting key function

🟡 **L41** [技术债务]: support nested CHOICE ordering


### venv/lib/python3.13/site-packages/pyasn1/codec/cer/decoder.py

🟡 **L51** [技术债务]: prohibit non-canonical encoding


### venv/lib/python3.13/site-packages/pyasn1/codec/ber/decoder.py

🟡 **L1378** [技术债务]: Seems not to be tested

🟡 **L1427** [技术债务]: Weird


### venv/lib/python3.13/site-packages/pyasn1/codec/ber/encoder.py

🟡 **L189** [技术债务]: try to avoid ASN.1 schema instantiation

🟡 **L557** [技术债务]: handling three flavors of input is too much -- split over codecs


### venv/lib/python3.13/site-packages/backtrader/feeds/vchartfile.py

🟡 **L64** [技术债务]: find reference to tick counter for format


### venv/lib/python3.13/site-packages/networkx/drawing/nx_latex.py

🟡 **L214** [技术债务]: allow pos to be None and use a nice TikZ default

🟡 **L277** [技术债务]: -- handle bending of multiedges


### venv/lib/python3.13/site-packages/networkx/drawing/layout.py

🟡 **L795** [技术债务]: revisit w/ sparse 1D container


### venv/lib/python3.13/site-packages/networkx/drawing/nx_pylab.py

🟡 **L2456** [技术债务]: should this be list or array (as in a numpy array)?


### venv/lib/python3.13/site-packages/networkx/algorithms/similarity.py

🟡 **L686** [技术债务]: support DiGraph


### venv/lib/python3.13/site-packages/networkx/algorithms/dag.py

🟡 **L1174** [技术债务]: In Python 3, this would be better as `yield from ...`.


### venv/lib/python3.13/site-packages/networkx/algorithms/distance_regular.py

🟡 **L218** [技术债务]: There is a definition for directed strongly regular graphs.


### venv/lib/python3.13/site-packages/networkx/algorithms/cycles.py

🟡 **L841** [技术债务]: use set for speedup?


### venv/lib/python3.13/site-packages/networkx/algorithms/efficiency_measures.py

🟡 **L118** [技术债务]: This can be made more efficient by computing all pairs shortest


### venv/lib/python3.13/site-packages/networkx/algorithms/cuts.py

🟡 **L322** [技术债务]: What is the generalization to two arguments, S and T? Does the


### venv/lib/python3.13/site-packages/networkx/generators/degree_seq.py

🟡 **L695** [技术债务]: Does this need to be sorted in reverse order?


### venv/lib/python3.13/site-packages/networkx/generators/geometric.py

🟡 **L190** [技术债务]: Is this function just a special case of the geographical


### venv/lib/python3.13/site-packages/networkx/generators/community.py

🟡 **L1034** [技术债务]: The original code incremented the number of iterations each


### venv/lib/python3.13/site-packages/networkx/algorithms/tree/mst.py

🟡 **L124** [技术债务]: This can be parallelized, both in the outer loop over

🟡 **L132** [技术债务]: This loop can be parallelized, to an extent (the union


### venv/lib/python3.13/site-packages/networkx/algorithms/isomorphism/ismags.py

🟡 **L514** [技术债务]: allow for precomputed partitions and colors

🟡 **L598** [技术债务]: remove these two if-checks when confident they never arise


### venv/lib/python3.13/site-packages/networkx/algorithms/isomorphism/isomorphvf2.py

🟡 **L217** [技术债务]: :


### venv/lib/python3.13/site-packages/networkx/algorithms/isomorphism/vf2pp.py

🟡 **L353** [技术债务]: do we need Ti_tilde_in? What nodes does it have?

🟡 **L450** [技术债务]: make the 4th argument the degree of u


### venv/lib/python3.13/site-packages/networkx/algorithms/connectivity/edge_kcomponents.py

🟡 **L97** [技术债务]: investigate https://arxiv.org/abs/1412.6466 for k=2


### venv/lib/python3.13/site-packages/networkx/algorithms/approximation/traveling_salesman.py

🟡 **L805** [技术债务]: this branch does not restore original_edge_weights of G!


### venv/lib/python3.13/site-packages/networkx/algorithms/approximation/dominating_set.py

🟡 **L22** [技术债务]: Why doesn't this algorithm work for directed graphs?


### venv/lib/python3.13/site-packages/networkx/algorithms/centrality/reaching.py

🟡 **L111** [技术债务]: This can be trivially parallelized.

🟡 **L206** [技术债务]: This can be trivially parallelized.


### venv/lib/python3.13/site-packages/networkx/algorithms/tests/test_swap.py

🟡 **L40** [技术债务]: Rewrite function to explicitly check for impossible swaps and raise error


### venv/lib/python3.13/site-packages/networkx/algorithms/bipartite/redundancy.py

🟡 **L93** [技术债务]: This can be trivially parallelized.


### venv/lib/python3.13/site-packages/networkx/algorithms/bipartite/matching.py

🟡 **L276** [技术债务]: - The lines between --- were unused and were thus commented

🟡 **L282** [技术债务]: Why is extra inner loop necessary?

🟡 **L287** [技术债务]: Originally, this function returned a three-tuple:


### venv/lib/python3.13/site-packages/networkx/algorithms/shortest_paths/weighted.py

🟡 **L1160** [技术债务]: This can be trivially parallelized.


### venv/lib/python3.13/site-packages/networkx/algorithms/shortest_paths/unweighted.py

🟡 **L221** [技术债务]: This can be trivially parallelized.

🟡 **L535** [技术债务]: This can be trivially parallelized.


### venv/lib/python3.13/site-packages/networkx/algorithms/coloring/equitable_coloring.py

🟡 **L163** [技术债务]: Checking whether a color has been visited can be made faster by


### venv/lib/python3.13/site-packages/networkx/algorithms/bipartite/tests/test_matching.py

🟡 **L110** [技术债务]: Assert that the vertices are the correct ones.


### venv/lib/python3.13/site-packages/networkx/algorithms/shortest_paths/tests/test_weighted.py

🟡 **L890** [技术债务]: nx.goldberg_radzik(D, 1)


### venv/lib/python3.13/site-packages/networkx/algorithms/assortativity/tests/test_connectivity.py

🟡 **L138** [技术债务]: Is this really the intended behavior for providing a


### venv/lib/python3.13/site-packages/networkx/generators/tests/test_expanders.py

🟡 **L37** [技术债务]: The second largest eigenvalue should be smaller than a constant,


### venv/lib/python3.13/site-packages/river/metrics/mutual_info.py

🟡 **L105** [技术债务]: confirm if we need to clip here


### venv/lib/python3.13/site-packages/river/ensemble/streaming_random_patches.py

🟡 **L547** [技术债务]: Find a way to verify if the model natively supports sample_weight (w)

🟡 **L849** [技术债务]: Find a way to verify if the model natively supports sample_weight (w)


### venv/lib/python3.13/site-packages/river/cluster/odac.py

🟡 **L465** [技术债务]: not sure if this is the best design


### venv/lib/python3.13/site-packages/river/datasets/test_datasets.py

🟡 **L75** [技术债务]: test the following synth datasets also


### venv/lib/python3.13/site-packages/river/linear_model/test_glm.py

🟡 **L102** [技术债务]: reactivate this check

🟡 **L106** [技术债务]: decrease the tolerance


### venv/lib/python3.13/site-packages/river/linear_model/bayesian_lin_reg.py

🟡 **L188** [技术债务]: we use standard matrix inversion. This is not very efficient. However, we don't


### venv/lib/python3.13/site-packages/river/utils/inspect.py

🟡 **L16** [技术债务]: maybe all of this could be done by monkeypatching isintance for pipelines?


### venv/lib/python3.13/site-packages/river/utils/math.py

🟡 **L372** [技术债务]: if |a - b| > 50 skip


### venv/lib/python3.13/site-packages/river/bandit/test_policies.py

🟡 **L74** [技术债务]: add simpler environments to test with


### venv/lib/python3.13/site-packages/river/bandit/evaluate.py

🟡 **L260** [技术债务]: use inverse propensity scoring


### venv/lib/python3.13/site-packages/river/proba/gaussian.py

🟡 **L273** [技术债务]: add support for weighted samples

🟡 **L277** [技术债务]: add support for weighted samples

🟡 **L288** [技术债务]: validate occurrence of ValueError

🟡 **L292** [技术债务]: validate occurrence of OverflowError


### venv/lib/python3.13/site-packages/river/base/test_base.py

🟡 **L61** [技术债务]: we could create a table of expected values for each platform and Python version


### venv/lib/python3.13/site-packages/river/stats/test_stats.py

🟡 **L139** [技术债务]: we shouldn't ignore these types

🟡 **L182** [技术债务]: we shouldn't ignore these types

🟡 **L206** [技术债务]: we shouldn't ignore these types


### venv/lib/python3.13/site-packages/river/stats/test_parallel.py

🟡 **L31** [技术债务]: clone should work instead of deepcopy


### venv/lib/python3.13/site-packages/river/tree/split_criterion/info_gain_split_criterion.py

🟡 **L50** [技术债务]: How small can d be before log2 overflows?


### venv/lib/python3.13/site-packages/cvxpy/interface/matrix_utilities.py

🟡 **L281** [技术债务]: catch complex symmetric but not Hermitian?


### venv/lib/python3.13/site-packages/cvxpy/atoms/matrix_frac.py

🟡 **L38** [技术债务]: raise error if not invertible?


### venv/lib/python3.13/site-packages/cvxpy/atoms/eye_minus_inv.py

🟡 **L115** [技术债务]: (akshayka): Figure out monotonicity.


### venv/lib/python3.13/site-packages/cvxpy/atoms/norm.py

🟡 **L74** [技术债务]: should not work for vectors.


### venv/lib/python3.13/site-packages/cvxpy/atoms/__init__.py

🟡 **L118** [技术债务]: (akshayka): Perhaps couple this information with the atom classes


### venv/lib/python3.13/site-packages/cvxpy/atoms/von_neumann_entr.py

🟡 **L127** [技术债务]: have to wrap derivative around scipy CSC sparse matrices


### venv/lib/python3.13/site-packages/cvxpy/atoms/quad_form.py

🟡 **L282** [技术债务]: allow indefinite quad_form


### venv/lib/python3.13/site-packages/cvxpy/atoms/harmonic_mean.py

🟡 **L39** [技术债务]: (akshayka): Behavior of the below is incorrect when x has negative


### venv/lib/python3.13/site-packages/cvxpy/constraints/constraint.py

🟡 **L43** [技术债务]: cast constants.

🟡 **L299** [技术债务]: (rileyjmurray): add a function to compute dual-variable violation.


### venv/lib/python3.13/site-packages/cvxpy/constraints/finite_set.py

🟡 **L91** [技术债务]: expand to parameterized sets.


### venv/lib/python3.13/site-packages/cvxpy/constraints/power.py

🟡 **L248** [技术债务]: support arbitrary z.dim


### venv/lib/python3.13/site-packages/cvxpy/tests/test_derivative.py

🟡 **L213** [技术债务]: (akshayka): too low but this problem is ill-conditioned

🟡 **L253** [技术债务]: (akshayka): This tolerance is too low.

🟡 **L771** [技术债务]: (akshayka): pf matrix completion not differentiable ...?


### venv/lib/python3.13/site-packages/cvxpy/tests/test_param_quad_prog.py

🟡 **L112** [技术债务]: Add derivatives and adjoint tests


### venv/lib/python3.13/site-packages/cvxpy/tests/test_valinvec2mixedint.py

🟡 **L393** [技术债务]: get parameters working.


### venv/lib/python3.13/site-packages/cvxpy/tests/test_dpp.py

🟡 **L303** [技术债务]: (akshayka): Try to emit DPP problems in Dqcp2Dcp


### venv/lib/python3.13/site-packages/cvxpy/tests/test_constraints.py

🟡 **L507** [技术债务]: other constraints


### venv/lib/python3.13/site-packages/cvxpy/tests/solver_test_helpers.py

🟡 **L74** [技术债务]: once dual variables are stored for attributes

🟡 **L86** [技术债务]: move this to Inequality.dual_violation

🟡 **L102** [技术债务]: once dual variables are stored for attributes

🟡 **L1589** [技术债务]: Assertions for dual variables for constraints specified via Variables attributes,


### venv/lib/python3.13/site-packages/cvxpy/tests/test_problem.py

🟡 **L266** [技术债务]: (akshayka): We cannot test whether the coefficients or

🟡 **L444** [技术债务]: (akshayka): Adapt this test to the reduction infrastructure.

🟡 **L483** [技术债务]: (akshayka): Adapt this test to the reduction infrastructure.

🟡 **L1948** [技术债务]: add -1, .5, .3, -2.3 and testing positivity constraints


### venv/lib/python3.13/site-packages/cvxpy/tests/test_linear_cone.py

🟡 **L72** [技术债务]: Maximize

🟡 **L105** [技术债务]: Maximize


### venv/lib/python3.13/site-packages/cvxpy/tests/test_conic_solvers.py

🟡 **L2613** [技术债务]: doesn't work on windows.


### venv/lib/python3.13/site-packages/cvxpy/tests/test_examples.py

🟡 **L46** [技术债务]: have atoms compute values for constants.


### venv/lib/python3.13/site-packages/cvxpy/tests/test_attributes.py

🟡 **L352** [技术债务]: make parameter validation work for multiple attributes.

🟡 **L371** [技术债务]: make parameter validation work for multiple attributes.

🟡 **L394** [技术债务]: make parameter validation work for multiple attributes.

🟡 **L467** [技术债务]: make parameter validation work for multiple attributes.


### venv/lib/python3.13/site-packages/cvxpy/problems/problem.py

🟡 **L1246** [技术债务]: (akshayka): Backpropagate through dual variables as well.

🟡 **L1331** [技术债务]: (akshayka): Forward differentiate dual variables as well


### venv/lib/python3.13/site-packages/cvxpy/problems/iterative.py

🟡 **L105** [技术债务]: take in vector.


### venv/lib/python3.13/site-packages/cvxpy/lin_ops/tree_mat.py

🟡 **L367** [技术债务]: what if constraints is empty?


### venv/lib/python3.13/site-packages/cvxpy/utilities/key_utils.py

🟡 **L24** [技术债务]: (akshayka): This module needs to be updated in order to handle


### venv/lib/python3.13/site-packages/cvxpy/utilities/perspective_utils.py

🟡 **L34** [技术债务]: Figure out how to instantiate Ax+b in SOC where we know which


### venv/lib/python3.13/site-packages/cvxpy/utilities/canonical.py

🟡 **L56** [技术债务]: (akshayka): some code relies on these not being cached, figure out


### venv/lib/python3.13/site-packages/cvxpy/utilities/coeff_extractor.py

🟡 **L34** [技术债务]: find best format for sparse matrices: csr, csc, dok, lil, ...

🟡 **L113** [技术债务]: keep sparse.


### venv/lib/python3.13/site-packages/cvxpy/transforms/partial_optimize.py

🟡 **L263** [技术债务]: better way to get constraint expressions.


### venv/lib/python3.13/site-packages/cvxpy/expressions/__init__.py

🟡 **L17** [技术债务]: export high level?


### venv/lib/python3.13/site-packages/cvxpy/expressions/variable.py

🟡 **L80** [技术债务]: (akshayka): Do not assume shape is 2D.


### venv/lib/python3.13/site-packages/cvxpy/reductions/cvx_attr2constr.py

🟡 **L93** [技术债务]: keep sparse / return coo_tensor


### venv/lib/python3.13/site-packages/cvxpy/reductions/canonicalization.py

🟡 **L101** [技术债务]: don't copy affine expressions?


### venv/lib/python3.13/site-packages/cvxpy/atoms/affine/affine_atom.py

🟡 **L95** [技术债务]: is this right?

🟡 **L127** [技术债务]: should be a simple function in cvxcore for this.


### venv/lib/python3.13/site-packages/cvxpy/atoms/affine/kron.py

🟡 **L30** [技术债务]: (akshayka): make DGP-compatible


### venv/lib/python3.13/site-packages/cvxpy/atoms/affine/conv.py

🟡 **L75** [技术债务]: support a non-constant first argument.

🟡 **L156** [技术债务]: work with right hand constant.

🟡 **L157** [技术债务]: (akshayka): make DGP-compatible

🟡 **L176** [技术债务]: support a non-constant first argument.


### venv/lib/python3.13/site-packages/cvxpy/atoms/elementwise/entr.py

🟡 **L23** [技术债务]: (akshayka): DGP support.


### venv/lib/python3.13/site-packages/cvxpy/atoms/elementwise/huber.py

🟡 **L23** [技术债务]: (akshayka): DGP support.


### venv/lib/python3.13/site-packages/cvxpy/cvxcore/python/__init__.py

🟡 **L8** [技术债务]: (akshayka): This is a hack; the swig-auto-generated cvxcore.py


### venv/lib/python3.13/site-packages/cvxpy/reductions/complex2real/complex2real.py

🟡 **L360** [技术债务]: don't copy affine expressions?


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/cone_matrix_stuffing.py

🟡 **L146** [技术债务]: (akshayka): unit tests

🟡 **L200** [技术债务]: technically part of inverse data.

🟡 **L290** [技术债务]: make this faster by intelligently operating on the

🟡 **L471** [技术债务]: rationalize Exponential.


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/dcp2cone.py

🟡 **L172** [技术债务]: don't copy affine expressions?


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/intermediate_chain.py

🟡 **L57** [技术债务]: Handle boolean constraints.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/utilities.py

🟡 **L85** [技术债务]: reshape based on dual variable size.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/bisection.py

🟡 **L34** [技术债务]: (akshayka): Try to emit DPP problems in Dqcp2Dcp

🟡 **L51** [技术债务]: (akshayka): Eliminate the need for reconstructing the problem


### venv/lib/python3.13/site-packages/cvxpy/reductions/cone2cone/exact.py

🟡 **L258** [技术债务]: Ideally we should construct x,y,z,alpha_p3d by


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/quad_form_canon.py

🟡 **L27** [技术债务]: this doesn't work with parameters!


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/__init__.py

🟡 **L66** [技术债务]: remove pwl canonicalize methods, use EliminatePwl reduction instead


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/huber_canon.py

🟡 **L33** [技术债务]: (akshayka): Make use of recursion inherent to canonicalization


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/entr_canon.py

🟡 **L30** [技术债务]: (akshayka): ExpCone requires each of its inputs to be a Variable;


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/log_canon.py

🟡 **L32** [技术债务]: (akshayka): ExpCone requires each of its inputs to be a Variable;


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/mul_canon.py

🟡 **L6** [技术债务]: (akshayka): expose as a reduction for user's convenience

🟡 **L9** [技术债务]: Only descend if both sides have parameters


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/quad/quad_over_lin_canon.py

🟡 **L35** [技术债务]: this codepath produces an intermediate dense matrix.


### venv/lib/python3.13/site-packages/cvxpy/reductions/dcp2cone/canonicalizers/quad/huber_canon.py

🟡 **L35** [技术债务]: (akshayka): Make use of recursion inherent to canonicalization


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/conic_solver.py

🟡 **L276** [技术债务]: (akshayka): profile to see whether using linear operators


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/cbc_conif.py

🟡 **L71** [技术债务]: check if is matrix stuffed.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/glop_conif.py

🟡 **L85** [技术债务]: Switch to a vectorized model-building interface when one is


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/mosek_conif.py

🟡 **L150** [技术债务]: check if is matrix stuffed.

🟡 **L164** [技术债务]: investigate how to transform or represent "A_psd" so that the following


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/scs_conif.py

🟡 **L185** [技术债务]: expand primal and dual variables from lower triangular to full.

🟡 **L186** [技术债务]: but this makes map from solution to variables not a slice.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/clarabel_conif.py

🟡 **L57** [技术债务]: On the right hand side, we may want to


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/xpress_conif.py

🟡 **L112** [技术债务]: check if is matrix stuffed.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/diffcp_conif.py

🟡 **L107** [技术债务]: expand primal and dual variables from lower triangular to full.

🟡 **L108** [技术债务]: but this makes map from solution to variables not a slice.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/cplex_conif.py

🟡 **L228** [技术债务]: check if is matrix stuffed.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/cvxopt_conif.py

🟡 **L83** [技术债务]: check if is matrix stuffed.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/highs_conif.py

🟡 **L323** [技术债务]: Names can be collected upstream more systematically


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/conic_solvers/gurobi_conif.py

🟡 **L76** [技术债务]: check if is matrix stuffed.

🟡 **L246** [技术债务]: add all SOC constrs at once! Be careful with return values

🟡 **L266** [技术债务]: user option to not compute duals.


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/qp_solvers/daqp_qpif.py

🟡 **L39** [技术债务]: to be tested


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/qp_solvers/copt_qpif.py

🟡 **L179** [技术债务]: switch to `P = P.tocoo()` when COPT supports sparray


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/qp_solvers/highs_qpif.py

🟡 **L222** [技术债务]: Names can be collected upstream more systematically


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/nlp_solvers/diff_engine/registry.py

🟡 **L214** [技术债务]: add support for diag vec with k

🟡 **L226** [技术债务]: add support for producing (1, n) directly in C and remove this reshape

🟡 **L227** [技术债务]: also raise error that the k should be zero, since that's the only supported case


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/nlp_solvers/diff_engine/converters.py

🟡 **L66** [技术债务]: we should support sparse elementwise multiply at some point.

🟡 **L113** [技术债务]: maybe multiply doesn't need parameter dict special case


### venv/lib/python3.13/site-packages/cvxpy/reductions/solvers/nlp_solvers/diff_engine/helpers.py

🟡 **L101** [技术债务]: this is a bit hacky, potentially we can just store the initial


### venv/lib/python3.13/site-packages/cvxpy/reductions/dgp2dcp/canonicalizers/mulexpression_canon.py

🟡 **L31** [技术债务]: (akshayka): Parallelize this for large matrices.


### venv/lib/python3.13/site-packages/cvxpy/reductions/eliminate_pwl/canonicalizers/norm1_canon.py

🟡 **L30** [技术债务]: (akshayka): Express this more naturally (recursively), in terms


### venv/lib/python3.13/site-packages/docker/types/services.py

🟡 **L328** [技术债务]: That windows condition will fail earlier since we


### venv/lib/python3.13/site-packages/docker/models/swarm.py

🟡 **L20** [技术债务]: https://github.com/docker/docker/issues/29192


### venv/lib/python3.13/site-packages/docker/api/swarm.py

🟡 **L288** [技术债务]: Temporary workaround for 1.13.0-rc bug


### venv/lib/python3.13/site-packages/sqlparse/filters/right_margin.py

🟡 **L13** [技术债务]: Doesn't work


### venv/lib/python3.13/site-packages/sqlparse/filters/others.py

🟡 **L19** [技术债务]: (andi) Comment types should be unified, see related issue38


### venv/lib/python3.13/site-packages/sqlparse/engine/grouping.py

🟡 **L359** [技术债务]: convert this to eidx instead of end token.


### venv/lib/python3.13/site-packages/sqlparse/engine/statement_splitter.py

🟡 **L60** [技术债务]: (andi): This makes no sense.  ## this comment neither


### venv/lib/python3.13/site-packages/sympy/series/gruntz.py

🟡 **L633** [技术债务]: this should not be necessary


### venv/lib/python3.13/site-packages/sympy/core/facts.py

🟡 **L310** [技术债务]: write more?

🟡 **L398** [技术债务]: b | c


### venv/lib/python3.13/site-packages/sympy/core/add.py

🟡 **L292** [技术债务]: zerocopy?


### venv/lib/python3.13/site-packages/sympy/core/exprtools.py

🟡 **L252** [技术债务]: after dropping python 3.7 support, use overload and Literal


### venv/lib/python3.13/site-packages/sympy/core/symbol.py

🟡 **L637** [技术债务]: add check against another Wild


### venv/lib/python3.13/site-packages/sympy/core/numbers.py

🟡 **L180** [技术债务]: we should use the warnings module

🟡 **L278** [技术债务]: caching with decorator, but not to degrade performance

🟡 **L1885** [技术债务]: make it decorator + bytecodehacks?


### venv/lib/python3.13/site-packages/sympy/core/mul.py

🟡 **L435** [技术债务]: Make non-commutative exponents not combine automatically

🟡 **L1049** [技术债务]: Should these be self.func?

🟡 **L1190** [技术债务]: Should this be self.func?

🟡 **L1617** [技术债务]: is_positive/is_negative is False doesn't take account of


### venv/lib/python3.13/site-packages/sympy/core/function.py

🟡 **L212** [技术债务]: Look at nargs

🟡 **L1416** [技术债务]: check if assumption of discontinuous derivatives exist

🟡 **L1673** [技术债务]: deprecate?  YES, make this 'enumerated_variables' and

🟡 **L1675** [技术债务]: support for `d^n`?


### venv/lib/python3.13/site-packages/sympy/core/expr.py

🟡 **L3692** [技术债务]: Smarter heuristics


### venv/lib/python3.13/site-packages/sympy/polys/ring_series.py

🟡 **L1977** [技术债务]: Use _parallel_dict_from_expr instead of sring as sring is


### venv/lib/python3.13/site-packages/sympy/polys/polyroots.py

🟡 **L761** [技术债务]: This is fragile. Figure out how to make this independent of construct_domain().


### venv/lib/python3.13/site-packages/sympy/polys/polyutils.py

🟡 **L378** [技术债务]: Integrate this into expand() itself


### venv/lib/python3.13/site-packages/sympy/polys/modulargcd.py

🟡 **L2129** [技术债务]: add support for algebraic function fields


### venv/lib/python3.13/site-packages/sympy/polys/rings.py

🟡 **L163** [技术债务]: rewrite this so that it doesn't use expand() (see poly()).

🟡 **L467** [技术债务]: should AlgebraicField be a Composite domain?

🟡 **L1251** [技术债务]: use an actual density measure

🟡 **L2275** [技术债务]: don't use dense representation (port PRS algorithms)

🟡 **L3044** [技术债务]: following methods should point to polynomial


### venv/lib/python3.13/site-packages/sympy/polys/distributedmodules.py

🟡 **L515** [技术债务]: better data structure!!!

🟡 **L675** [技术债务]: apply the product criterion?

🟡 **L683** [技术债务]: mergesort?


### venv/lib/python3.13/site-packages/sympy/holonomic/holonomic.py

🟡 **L868** [技术债务]: support for singular initial condition


### venv/lib/python3.13/site-packages/sympy/printing/str.py

🟡 **L962** [技术债务]: : Handle indices


### venv/lib/python3.13/site-packages/sympy/printing/llvmjitcode.py

🟡 **L95** [技术债务]: - assumes all called functions take one double precision argument.


### venv/lib/python3.13/site-packages/sympy/printing/tensorflow.py

🟡 **L107** [技术债务]: a better class structure would avoid this mess:

🟡 **L202** [技术债务]: is this necessary?


### venv/lib/python3.13/site-packages/sympy/printing/smtlib.py

🟡 **L189** [技术债务]: Sympy does not support quantifiers yet as of 2022, but quantifiers can be handy in SMT.


### venv/lib/python3.13/site-packages/sympy/printing/latex.py

🟡 **L238** [技术债务]: merge this with the above, which requires a lot of test changes

🟡 **L1176** [技术债务]: should exp_polar be printed differently?

🟡 **L2585** [技术债务]: incorporate order

🟡 **L2777** [技术债务]: This expression is potentially confusing,

🟡 **L2785** [技术债务]: nicer fractions for few generators...

🟡 **L2802** [技术债务]: nicer fractions for few generators...

🟡 **L2850** [技术债务]: Handle indices


### venv/lib/python3.13/site-packages/sympy/printing/octave.py

🟡 **L258** [技术债务]: how to do better, e.g., for octave_code(2*GoldenRatio)?


### venv/lib/python3.13/site-packages/sympy/solvers/recurr.py

🟡 **L564** [技术债务]: The call to rsolve_ratio below should suffice (rsolve_poly


### venv/lib/python3.13/site-packages/sympy/solvers/bivariate.py

🟡 **L34** [技术债务]: it would be good to pick the smallest divisible power


### venv/lib/python3.13/site-packages/sympy/solvers/solvers.py

🟡 **L2902** [技术债务]: option for calculating J numerically


### venv/lib/python3.13/site-packages/sympy/solvers/pde.py

🟡 **L284** [技术债务]: : For now pde.py uses support offered by the ode_order function

🟡 **L521** [技术债务]: : For now homogeneous first order linear PDE's having

🟡 **L611** [技术债务]: : For now homogeneous first order linear PDE's having

🟡 **L937** [技术债务]: Find lcm() of all the divisors and divide with it, instead of


### venv/lib/python3.13/site-packages/sympy/solvers/solveset.py

🟡 **L694** [技术债务]: : We should not blindly recurse through all args of arbitrary expressions like this

🟡 **L966** [技术债务]: This solver can be extended to hyperbolics if the

🟡 **L972** [技术债务]: The pre-processing below (extraction of numerators, denominators,

🟡 **L1662** [技术债务]: Case: A-> function of symbol, can be extended here


### venv/lib/python3.13/site-packages/sympy/codegen/rewriting.py

🟡 **L330** [技术债务]: We should be able to support more than 2 elements


### venv/lib/python3.13/site-packages/sympy/utilities/codegen.py

🟡 **L249** [技术债务]: :

🟡 **L1530** [技术债务]: this is probably general enough for other high-level


### venv/lib/python3.13/site-packages/sympy/testing/runtests.py

🟡 **L1936** [技术债务]: parse integers as well ?

🟡 **L2023** [技术债务]: Should these be protected?


### venv/lib/python3.13/site-packages/sympy/integrals/laplace.py

🟡 **L400** [技术债务]: rules with sqrt(a*t) and sqrt(a/t) have stopped working after


### venv/lib/python3.13/site-packages/sympy/integrals/meijerint.py

🟡 **L119** [技术债务]: this needs more polar_lift (c/f entry for exp)

🟡 **L164** [技术债务]: can do sin^n, sinh^n by expansion ... where?

🟡 **L170** [技术债务]: can do t + a. but can also do by expansion... (XXX not really)

🟡 **L187** [技术债务]: these only hold for positive p, and can be made more general

🟡 **L189** [技术债务]: also it would be nice to derive them recursively ...

🟡 **L202** [技术债务]: log(x)/(x+a) and log(x)/(x-1) can also be done. should they

🟡 **L204** [技术债务]: further formulae in this section seem obscure

🟡 **L230** [技术债务]: exp(-x)*erf(I*x) does not work

🟡 **L256** [技术债务]: all of the following should be derivable

🟡 **L282** [技术债务]: many more formulas. should all be derivable

🟡 **L286** [技术债务]: many more formulas. should all be derivable

🟡 **L524** [技术债务]: should this be a method of meijerg?

🟡 **L852** [技术债务]: altered cases 4-7

🟡 **L876** [技术债务]: This leaves only one case from the three listed by Prudnikov.

🟡 **L972** [技术债务]: should we try both?


### venv/lib/python3.13/site-packages/sympy/integrals/transforms.py

🟡 **L201** [技术债务]: handle derivatives etc


### venv/lib/python3.13/site-packages/sympy/integrals/prde.py

🟡 **L114** [技术债务]: Merge this with the very similar special_denom() in rde.py

🟡 **L158** [技术债务]: Add test

🟡 **L878** [技术债务]: finish writing this and write tests

🟡 **L921** [技术债务]: We treat this as 'no solution', until the structure

🟡 **L952** [技术债务]: Write the full algorithm using the structure theorems.

🟡 **L1035** [技术债务]: What should really be done in this case?

🟡 **L1160** [技术债务]: What should really be done in this case?

🟡 **L1185** [技术债务]: But maybe we can tell if they're not rational, like

🟡 **L1266** [技术债务]: finish writing this and write tests

🟡 **L1301** [技术债务]: we can use more efficient residue reduction from ratint()


### venv/lib/python3.13/site-packages/sympy/integrals/deltafunctions.py

🟡 **L144** [技术债务]: the second term tells whether is DeltaDirac or Derivative


### venv/lib/python3.13/site-packages/sympy/integrals/rde.py

🟡 **L38** [技术债务]: Add messages to NonElementaryIntegralException errors

🟡 **L205** [技术债务]: finish writing this and write tests

🟡 **L286** [技术债务]: finish writing this and write tests

🟡 **L510** [技术债务]: better name for this function

🟡 **L653** [技术债务]: Write a dummy function that does this idiom

🟡 **L713** [技术债务]: Is this check necessary, and if so, what should it do if it fails?


### venv/lib/python3.13/site-packages/sympy/integrals/intpoly.py

🟡 **L977** [技术债务]: : This part is quite hacky. Should be made more robust with

🟡 **L978** [技术债务]: : respect to symbol names and scalable w.r.t higher dimensions.


### venv/lib/python3.13/site-packages/sympy/integrals/heurisch.py

🟡 **L495** [技术债务]: caching is significant factor for why permutations work at all. Change this.

🟡 **L700** [技术债务]: Currently it's better to use symbolic expressions here instead

🟡 **L726** [技术债务]: Non-polynomial expression. This should have been


### venv/lib/python3.13/site-packages/sympy/integrals/risch.py

🟡 **L333** [技术债务]: This probably doesn't need to be completely recomputed at

🟡 **L366** [技术债务]: Would there ever be any benefit from just

🟡 **L395** [技术债务]: Just put it in self.Tfuncs

🟡 **L497** [技术债务]: Add something to backsubs to put exp(const*p)

🟡 **L530** [技术债务]: give algebraic dependence in error string

🟡 **L779** [技术债务]: Rewrite algorithms below to use this (?)

🟡 **L781** [技术债务]: Pass through information about why the integral was nonelementary,

🟡 **L798** [技术债务]: This should go in densetools.py.

🟡 **L855** [技术债务]: Use this on the final result.  That way, we can avoid answers like

🟡 **L1006** [技术债务]: This algorithm appears to be faster in every case

🟡 **L1007** [技术债务]: Verify this and splitfactor() for multiple extensions

🟡 **L1250** [技术债务]: also consider the complex roots which should

🟡 **L1280** [技术债务]: Use log_to_atan() from rationaltools.py

🟡 **L1350** [技术债务]: check what Lambda does with RootOf

🟡 **L1365** [技术债务]: verify that this is correct for multiple extensions

🟡 **L1458** [技术债务]: This does not do the right thing when b is False

🟡 **L1621** [技术债务]: Integral from k?

🟡 **L1622** [技术债务]: split out nonelementary integral

🟡 **L1691** [技术债务]: This is useful in and of itself, because isinstance(result,


### venv/lib/python3.13/site-packages/sympy/integrals/trigonometry.py

🟡 **L5** [技术债务]: sin(a*x)*cos(b*x) -> sin((a+b)x) + sin((a-b)x) ?


### venv/lib/python3.13/site-packages/sympy/integrals/manualintegrate.py

🟡 **L1587** [技术债务]: handle n < -1 case

🟡 **L2040** [技术债务]: This is for future development, as currently


### venv/lib/python3.13/site-packages/sympy/assumptions/refine.py

🟡 **L53** [技术债务]: this will probably not work with Integral or Polynomial


### venv/lib/python3.13/site-packages/sympy/assumptions/satask.py

🟡 **L103** [技术债务]: Run additional checks to see which combination of the


### venv/lib/python3.13/site-packages/sympy/plotting/plot.py

🟡 **L128** [技术债务]: _process_piecewise check goes here

🟡 **L204** [技术债务]: Add color arrays for plots.

🟡 **L205** [技术债务]: Add more plotting options for 3d plots.

🟡 **L206** [技术债务]: Adaptive sampling for 3D plots.


### venv/lib/python3.13/site-packages/sympy/plotting/series.py

🟡 **L381** [技术债务]: set cse=True once this issue is solved:

🟡 **L1146** [技术债务]: for now, I assume that numpy functions are going to succeed

🟡 **L1156** [技术债务]: what if points[k][idx]==e or points[k][idx+1]==e?

🟡 **L1774** [技术债务]: remove this

🟡 **L1790** [技术债务]: remove this

🟡 **L1871** [技术债务]: remove this

🟡 **L1972** [技术债务]: remove this

🟡 **L2094** [技术债务]: remove this


### venv/lib/python3.13/site-packages/sympy/plotting/utils.py

🟡 **L159** [技术债务]: prange check goes here


### venv/lib/python3.13/site-packages/sympy/plotting/experimental_lambdify.py

🟡 **L78** [技术债务]: debugging output


### venv/lib/python3.13/site-packages/sympy/sets/fancysets.py

🟡 **L1424** [技术债务]: This should probably be handled with something like:


### venv/lib/python3.13/site-packages/sympy/sets/sets.py

🟡 **L2555** [技术债务]: check subsets (`func` in `setv`)

🟡 **L2558** [技术债务]: support more


### venv/lib/python3.13/site-packages/sympy/combinatorics/coset_table.py

🟡 **L985** [技术债务]: complete the docstring


### venv/lib/python3.13/site-packages/sympy/combinatorics/fp_groups.py

🟡 **L353** [技术债务]: use |G:H| = |G|/|H| (currently H can't be made into a group)

🟡 **L903** [技术债务]: this should support input of a list of general words


### venv/lib/python3.13/site-packages/sympy/tensor/index_methods.py

🟡 **L150** [技术债务]: symmetries from power needs to check special cases, else nothing

🟡 **L196** [技术债务]: search for symmetries

🟡 **L279** [技术债务]: No support for Piecewise yet

🟡 **L449** [技术债务]: No support for Piecewise yet


### venv/lib/python3.13/site-packages/sympy/tensor/tensor.py

🟡 **L2208** [技术债务]: add possibility of metric after (spinors)

🟡 **L2590** [技术债务]: what is the part which is not a coeff?

🟡 **L3203** [技术债务]: put this into TensExpr?

🟡 **L3209** [技术债务]: put this into TensExpr?

🟡 **L3225** [技术债务]: inefficient, this should be done at root level only:

🟡 **L3268** [技术债务]: check data compatibility with properties of tensor.

🟡 **L3344** [技术债务]: replace .args[0] with .name:

🟡 **L3359** [技术债务]: if there is no metric present, the derivative should be zero?

🟡 **L3661** [技术债务]: this method should be private

🟡 **L3662** [技术债务]: should this method be renamed _from_components_free_dum ?

🟡 **L4540** [技术债务]: inherit dummies from expr

🟡 **L5136** [技术债务]: add a dum_to_components_map ?


### venv/lib/python3.13/site-packages/sympy/geometry/ellipse.py

🟡 **L666** [技术债务]: Replace solve with nonlinsolve, when nonlinsolve will be able to solve in real domain

🟡 **L919** [技术债务]: Replace solve with solveset, when this line is tested

🟡 **L927** [技术债务]: Replace solve with solveset, when these lines are tested

🟡 **L1290** [技术债务]: Replace solve with solveset, when this line is tested


### venv/lib/python3.13/site-packages/sympy/geometry/plane.py

🟡 **L412** [技术债务]: Replace solve with solveset, when this line is tested


### venv/lib/python3.13/site-packages/sympy/physics/paulialgebra.py

🟡 **L144** [技术债务]: don't work for -I*Pauli(2)*Pauli(3)


### venv/lib/python3.13/site-packages/sympy/physics/secondquant.py

🟡 **L2758** [技术债务]: If we arrive here, there are no ordered dummies. A method to


### venv/lib/python3.13/site-packages/sympy/calculus/util.py

🟡 **L327** [技术债务]: handle piecewise defined functions

🟡 **L328** [技术债务]: handle transcendental functions

🟡 **L329** [技术债务]: handle multivariate functions


### venv/lib/python3.13/site-packages/sympy/calculus/accumulationbounds.py

🟡 **L688** [技术债务]: : Devise a better method for Union of AccumBounds


### venv/lib/python3.13/site-packages/sympy/simplify/simplify.py

🟡 **L646** [技术债务]: Apply different strategies, considering expression pattern:

🟡 **L1087** [技术债务]: see if x*log(a)+x*log(a)*log(b) -> x*log(a)*(1+log(b))?


### venv/lib/python3.13/site-packages/sympy/simplify/gammasimp.py

🟡 **L393** [技术债务]: is there a better heuristic?


### venv/lib/python3.13/site-packages/sympy/simplify/hyperexpand.py

🟡 **L50** [技术债务]: work this out in detail.

🟡 **L86** [技术债务]: see if this can work as Mod(x, 1); this will require

🟡 **L253** [技术债务]: branching

🟡 **L736** [技术债务]: with symbolic parameters, it could be advantageous

🟡 **L1947** [技术债务]: tons of more formulae

🟡 **L2116** [技术债务]: for now, we use the following simple heuristic: inverse-shift

🟡 **L2245** [技术债务]: the following would be possible:

🟡 **L2250** [技术债务]: Also, we tend to create combinations of gamma functions that can be

🟡 **L2443** [技术债务]: it would be helpful to give conditions under which the integral


### venv/lib/python3.13/site-packages/sympy/vector/functions.py

🟡 **L158** [技术债务]: This gets a random coordinate system in case of multiple ones:

🟡 **L503** [技术债务]: : The following line introduces a performance issue


### venv/lib/python3.13/site-packages/sympy/vector/coordsysrect.py

🟡 **L702** [技术债务]: trigsimp is needed here so that the matrix becomes


### venv/lib/python3.13/site-packages/sympy/vector/operators.py

🟡 **L214** [技术债务]: is case of many coord systems, this gets a random one:


### venv/lib/python3.13/site-packages/sympy/diffgeom/diffgeom.py

🟡 **L26** [技术债务]: you are a bit excessive in the use of Dummies

🟡 **L27** [技术债务]: dummy point, literal field

🟡 **L28** [技术债务]: too often one needs to call doit or simplify on the output, check the

🟡 **L1101** [技术债务]: you need a real dummy function for the next line

🟡 **L1309** [技术债务]: this is ugly - the Commutator can be Zero and

🟡 **L1438** [技术债务]: the calculation of signatures is slow

🟡 **L1439** [技术债务]: you do not need all these permutations (neither the prefactor)

🟡 **L1594** [技术债务]: you need a real dummy function for the next line

🟡 **L1892** [技术债务]: Is this a good idea?

🟡 **L1919** [技术债务]: move some of this to class methods.

🟡 **L1920** [技术债务]: rewrite using the .as_blah_blah methods

🟡 **L1965** [技术债务]: move some of this to class methods.

🟡 **L1966** [技术债务]: rewrite using the .as_blah_blah methods


### venv/lib/python3.13/site-packages/sympy/stats/random_matrix_models.py

🟡 **L249** [技术债务]: : Add support for Lie groups(as extensions of sympy.diffgeom)


### venv/lib/python3.13/site-packages/sympy/stats/joint_rv.py

🟡 **L415** [技术债务]: Modify to support integration


### venv/lib/python3.13/site-packages/sympy/stats/rv.py

🟡 **L1323** [技术债务]: : Remove when lambdify accepts 'pymc' as module

🟡 **L1340** [技术债务]: Replace the try-except block with only given_fn(*args)

🟡 **L1366** [技术债务]: Replace the try-except block with only given_fn(*args)

🟡 **L1383** [技术债务]: Replace the try-except block with only fn(*args)

🟡 **L1610** [技术债务]: do this for drv.py and frv.py if necessary.

🟡 **L1611** [技术债务]: add more distributions here if there are more


### venv/lib/python3.13/site-packages/sympy/stats/joint_rv_types.py

🟡 **L134** [技术债务]: Add support for sets provided by the user


### venv/lib/python3.13/site-packages/sympy/stats/matrix_distributions.py

🟡 **L114** [技术债务]: Add tests after adding matrix distributions in numpy_rv_map


### venv/lib/python3.13/site-packages/sympy/stats/drv.py

🟡 **L152** [技术债务]: support discrete sets with non integer stepsizes


### venv/lib/python3.13/site-packages/sympy/series/tests/test_order.py

🟡 **L162** [技术债务]: : A better output for Order(log(x) + 1/log(x))


### venv/lib/python3.13/site-packages/sympy/series/tests/test_gruntz.py

🟡 **L148** [技术债务]: zeta function series

🟡 **L152** [技术债务]: 8.35 - 8.37 (bessel, max-min)


### venv/lib/python3.13/site-packages/sympy/core/tests/test_basic.py

🟡 **L208** [技术债务]: UndefinedFunction does not subclass Expr


### venv/lib/python3.13/site-packages/sympy/core/tests/test_relational.py

🟡 **L617** [技术债务]: could replace with random selection after test passes

🟡 **L643** [技术债务]: could replace with random selection after test passes

🟡 **L925** [技术债务]: The test below fails because (-infx).is_extended_positive is True


### venv/lib/python3.13/site-packages/sympy/core/tests/test_diff.py

🟡 **L138** [技术债务]: assert diff(x**2, (x, n)) == x**(2-n)*ff(2, n)


### venv/lib/python3.13/site-packages/sympy/core/tests/test_facts.py

🟡 **L70** [技术债务]: move me to appropriate place


### venv/lib/python3.13/site-packages/sympy/core/tests/test_arit.py

🟡 **L1182** [技术债务]: The line below should be True rather than None

🟡 **L1198** [技术债务]: Should the line below be True rather than None?

🟡 **L2171** [技术债务]: This evaluates as:


### venv/lib/python3.13/site-packages/sympy/core/tests/test_assumptions.py

🟡 **L410** [技术债务]: Change to x.is_nonzero is None


### venv/lib/python3.13/site-packages/sympy/core/tests/test_function.py

🟡 **L1447** [技术债务]: Disable string inputs (https://github.com/sympy/sympy/issues/11003)


### venv/lib/python3.13/site-packages/sympy/core/tests/test_expr.py

🟡 **L917** [技术债务]: UndefinedFunction does not subclass Expr


### venv/lib/python3.13/site-packages/sympy/polys/domains/fractionfield.py

🟡 **L34** [技术债务]: remove this


### venv/lib/python3.13/site-packages/sympy/polys/domains/domain.py

🟡 **L459** [技术债务]: remove this branch


### venv/lib/python3.13/site-packages/sympy/polys/domains/polynomialring.py

🟡 **L40** [技术债务]: remove this


### venv/lib/python3.13/site-packages/sympy/polys/domains/quotientring.py

🟡 **L142** [技术债务]: optionally disable reduction?


### venv/lib/python3.13/site-packages/sympy/polys/tests/test_distributedmodules.py

🟡 **L50** [技术债务]: test to_dict?


### venv/lib/python3.13/site-packages/sympy/polys/tests/test_heuristicgcd.py

🟡 **L53** [技术债务]: assert heugcd(f, f.diff(x))[0] == g


### venv/lib/python3.13/site-packages/sympy/polys/numberfields/basis.py

🟡 **L216** [技术债务]: :


### venv/lib/python3.13/site-packages/sympy/polys/numberfields/primes.py

🟡 **L678** [技术债务]: (future work):


### venv/lib/python3.13/site-packages/sympy/polys/numberfields/modules.py

🟡 **L1839** [技术债务]: :


### venv/lib/python3.13/site-packages/sympy/polys/agca/modules.py

🟡 **L1281** [技术债务]: this can be done more efficiently


### venv/lib/python3.13/site-packages/sympy/polys/agca/ideals.py

🟡 **L102** [技术债务]: more


### venv/lib/python3.13/site-packages/sympy/polys/matrices/normalforms.py

🟡 **L11** [技术债务]: (future work):


### venv/lib/python3.13/site-packages/sympy/polys/matrices/dense.py

🟡 **L173** [技术债务]: Use a nontrivial pivoting strategy to control intermediate

🟡 **L321** [技术债务]: Use a non-trivial pivoting strategy. Even just row swapping makes a


### venv/lib/python3.13/site-packages/sympy/polys/matrices/_dfm.py

🟡 **L23** [技术债务]: :


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_theanocode.py

🟡 **L226** [技术债务]: - matrix broadcasting?


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_smtlib.py

🟡 **L457** [技术债务]: make smtlib_code support arrays

🟡 **L509** [技术债务]: make smtlib_code support arrays / matrices ?


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_latex.py

🟡 **L2079** [技术债务]: Handle indices


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_julia.py

🟡 **L184** [技术债务]: is it worth worrying about this?  Its not wrong, just

🟡 **L293** [技术债务]: ?


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_octave.py

🟡 **L243** [技术债务]: is it worth worrying about this?  Its not wrong, just

🟡 **L358** [技术债务]: ?


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_aesaracode.py

🟡 **L236** [技术债务]: - matrix broadcasting?


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_repr.py

🟡 **L93** [技术债务]: more tests

🟡 **L339** [技术债务]: sT fails because Cycle is not immutable and calling srepr(Cycle(1, 2))


### venv/lib/python3.13/site-packages/sympy/printing/pretty/pretty.py

🟡 **L1375** [技术债务]: Refactor this code and matrix into some tabular environment.

🟡 **L1442** [技术债务]: refactor Matrix, Piecewise, and this into a tabular environment

🟡 **L1490** [技术债务]: refactor Matrix, Piecewise, and this into a tabular environment

🟡 **L1574** [技术债务]: should exp_polar be printed differently?

🟡 **L1910** [技术债务]: Move this code to prettyForm

🟡 **L2239** [技术债务]: the stuff to the left of the | and the stuff to the right of

🟡 **L2602** [技术债务]: copy-pasted from _print_Function: can we do better?

🟡 **L2671** [技术债务]: incorporate order

🟡 **L2808** [技术债务]: Handle indices


### venv/lib/python3.13/site-packages/sympy/printing/pretty/pretty_symbology.py

🟡 **L200** [技术债务]: Make brackets adjust to height of contents

🟡 **L333** [技术债务]: robustify when no unicodedat available


### venv/lib/python3.13/site-packages/sympy/printing/pretty/tests/test_pretty.py

🟡 **L4575** [技术债务]: The "x in N" parts below should be centered independently of the

🟡 **L7256** [技术债务]: add support for ASCII pretty.

🟡 **L7620** [技术债务]: TBD polylog(s - 1, z)


### venv/lib/python3.13/site-packages/sympy/solvers/diophantine/diophantine.py

🟡 **L2566** [技术债务]: pre-simplification: Not necessary but may simplify

🟡 **L3893** [技术债务]: Fall back to diop_DN when k = 2


### venv/lib/python3.13/site-packages/sympy/solvers/tests/test_solvers.py

🟡 **L1727** [技术债务]: Investigate why currently solution [0] is preferred over [1].


### venv/lib/python3.13/site-packages/sympy/solvers/tests/test_polysys.py

🟡 **L185** [技术债务]: does this really have to be so complicated?!


### venv/lib/python3.13/site-packages/sympy/solvers/tests/test_solveset.py

🟡 **L323** [技术债务]: Is the above solution set definitely complete?

🟡 **L1862** [技术债务]: add more simple testcases when solveset returns


### venv/lib/python3.13/site-packages/sympy/solvers/ode/single.py

🟡 **L204** [技术债务]: Add methods that can be used by many ODE solvers:


### venv/lib/python3.13/site-packages/sympy/solvers/ode/ode.py

🟡 **L798** [技术债务]: Use solveset here

🟡 **L1072** [技术债务]: Hint first order series should match only if d/e is analytic.

🟡 **L1783** [技术债务]: if two solutions are solved for f(x), we still want to be


### venv/lib/python3.13/site-packages/sympy/solvers/ode/tests/test_systems.py

🟡 **L2480** [技术债务]: assert checksysodesol(eq3, sol3) == (True, [0, 0])

🟡 **L2485** [技术债务]: assert checksysodesol(eq4, sol4) == (True, [0, 0])

🟡 **L2516** [技术债务]: assert checksysodesol(eq1, sol1) == (True, [0, 0, 0])

🟡 **L2524** [技术债务]: assert checksysodesol(eq2, sol2) == (True, [0, 0, 0])


### venv/lib/python3.13/site-packages/sympy/solvers/ode/tests/test_ode.py

🟡 **L911** [技术债务]: The solution here should be O((x-2)**3) so is incorrect

🟡 **L929** [技术债务]: Solution should be O((x+2)**6)

🟡 **L948** [技术债务]: checkodesol fails for this solution...

🟡 **L956** [技术债务]: checkodesol fails for this solution...


### venv/lib/python3.13/site-packages/sympy/codegen/tests/test_rewriting.py

🟡 **L442** [技术债务]: this should ideally be automatically handled.


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_codegen_octave.py

🟡 **L83** [技术债务]: how to pass inline=False to the OctaveCodePrinter?

🟡 **L225** [技术债务]: how to pass inline=False to the OctaveCodePrinter?


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_codegen_rust.py

🟡 **L89** [技术债务]: how to pass inline to the RustCodePrinter?

🟡 **L248** [技术债务]: how to pass inline to the RustCodePrinter?


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_pickling.py

🟡 **L409** [技术债务]: Py3k

🟡 **L420** [技术债务]: AssertionError: assert id(obj) not in self.memo

🟡 **L424** [技术债务]: AssertionError: assert id(obj) not in self.memo

🟡 **L500** [技术债务]: AssertionError

🟡 **L504** [技术债务]: AttributeError: 'PolyElement' object has no attribute 'ring'

🟡 **L526** [技术债务]: Argh, Python is so naive. No lambdas nor inner function support in

🟡 **L559** [技术债务]: TypeError: __init__() takes at least 3 arguments (1 given)

🟡 **L563** [技术债务]: TypeError: can't pickle instancemethod objects

🟡 **L612** [技术债务]: PicklingError: Can't pickle <function <lambda> at 0x38578c0>: it's not found as __main__.<lambda>

🟡 **L622** [技术债务]: TypeError: __init__() takes at least 3 arguments (1 given)

🟡 **L639** [技术债务]: def test_pickling_polys_rootisolation():


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_wester.py

🟡 **L920** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L956** [技术债务]: Replace solve with solveset when it gives Lambert solution

🟡 **L966** [技术债务]: x = [-1, 2*(+/-asinh(1)*I + n*pi}, 3*(pi/6 + n*pi/3)]

🟡 **L967** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1014** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1032** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1038** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1047** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1052** [技术债务]: Replace solve with solveset, as of now test fails for solveset

🟡 **L1059** [技术债务]: Replace solve with solveset which gives both [+/- current answer]

🟡 **L1077** [技术债务]: Replace solve with solveset, as of now

🟡 **L1084** [技术债务]: Replace solve with solveset, as of now

🟡 **L1092** [技术债务]: Replace solve with solveset, as of now

🟡 **L1099** [技术债务]: Replace solve with solveset, as of now

🟡 **L1118** [技术债务]: Replace solve with solveset, as of now

🟡 **L1194** [技术债务]: Replace solve with solveset, as of now

🟡 **L2252** [技术债务]: Replace solve with solveset, current test fails for solveset

🟡 **L3082** [技术债务]: Replace solve with solveset, when it works for solveset


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_codegen_julia.py

🟡 **L85** [技术债务]: how to pass inline=False to the JuliaCodePrinter?

🟡 **L235** [技术债务]: how to pass inline=False to the JuliaCodePrinter?


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_codegen.py

🟡 **L16** [技术债务]: Fails due to circular import in with core


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_rde.py

🟡 **L71** [技术债务]: add more tests here

🟡 **L114** [技术债务]: Add test for when the degree bound becomes larger after limited_integrate

🟡 **L115** [技术债务]: Add test for db == da - 1 case

🟡 **L118** [技术债务]: Add tests

🟡 **L119** [技术债务]: Add test for when the degree becomes larger after parametric_log_deriv()

🟡 **L179** [技术债务]: Add more exp tests, including tests that require is_deriv_in_field()

🟡 **L193** [技术债务]: Add more primitive tests, including tests that require is_deriv_in_field()

🟡 **L197** [技术债务]: Add more tests for rischDE, including ones from the text


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_trigonometry.py

🟡 **L32** [技术债务]: remove conds='none' below. For this to work we would have to rule


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_risch.py

🟡 **L235** [技术债务]: Skip or make faster

🟡 **L250** [技术债务]: Add tests for integrate_hyperexponential() from the book

🟡 **L374** [技术债务]: Add a test where two different parts of the extension use a


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_prde.py

🟡 **L105** [技术债务]: when bound_degree() can handle this, test degree bound from that too

🟡 **L147** [技术债务]: Add test for deg(b) <= 0 with b small

🟡 **L262** [技术债务]: Add more tests

🟡 **L280** [技术债务]: Add more tests, including ones with exponentials


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_heurisch.py

🟡 **L221** [技术债务]: it looks like this used to work just by coincindence and

🟡 **L254** [技术债务]: heurisch() is off by a constant: -3/4. Possibly different permutation

🟡 **L343** [技术债务]: convert the rest of PMINT tests:


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_laplace.py

🟡 **L110** [技术债务]: rules with sqrt(a*t) and sqrt(a/t) have stopped working after

🟡 **L698** [技术债务]: sinh/cosh shifted come out a mess. also delayed trig is a mess

🟡 **L699** [技术债务]: should this simplify further?

🟡 **L714** [技术债务]: can we make erf(t) work?

🟡 **L756** [技术债务]: LT of Si, Shi, Chi is a mess ...


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_integrals.py

🟡 **L328** [技术债务]: Remove conds='none' below, let the assumption take care of it.

🟡 **L1140** [技术债务]: Remove conds='none' below, let the assumption take care of it.

🟡 **L1329** [技术债务]: How to test risch=False?


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_meijerint.py

🟡 **L149** [技术债务]: what simplifications should be done automatically?

🟡 **L165** [技术债务]: it would be nice to test the condition

🟡 **L245** [技术债务]: more orthogonality integrals

🟡 **L257** [技术债务]: can do higher powers, but come out as high order ... should they be

🟡 **L262** [技术债务]: more besseli when tables are extended or recursive mellin works

🟡 **L273** [技术债务]: how does besselj(0, a*x)*besselj(0, b*x) work?

🟡 **L274** [技术债务]: how does besselj(0, x)**2*besselj(1, x)**2 work?

🟡 **L275** [技术债务]: sin(x)*besselj(0, x) etc come out a mess

🟡 **L276** [技术债务]: can x*log(x)*besselj(0, x) be done?

🟡 **L277** [技术债务]: how does besselj(1, x)*besselj(0, x+a) work?

🟡 **L374** [技术债务]: gammasimp cannot prove that the factor is unity

🟡 **L517** [技术债务]: conditions are a mess

🟡 **L523** [技术债务]: gamma, rayleigh

🟡 **L544** [技术债务]: If alpha, beta are not declared as finite the line below hangs

🟡 **L579** [技术债务]: are there other distributions supported on (-oo, oo) that we can do?

🟡 **L658** [技术债务]: maybe simplify the inequalities? when the simplification

🟡 **L668** [技术债务]: FT(besselj(0,x)) - conditions are messy (but for acceptable reasons)


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_transforms.py

🟡 **L80** [技术债务]: does not work with bneg, argument wrong. Needs changes to matching.

🟡 **L164** [技术债务]: we cannot currently do these (needs summation of 3F2(-1))

🟡 **L244** [技术债务]: we can't do any of these (delicate cancellation)

🟡 **L253** [技术债务]: bessely(a, x)*besselk(a, x) is a mess

🟡 **L264** [技术债务]: products of besselk are a mess

🟡 **L271** [技术债务]: exp(x/2)*besselk(a, x/2) [etc] cannot currently be done

🟡 **L272** [技术债务]: various strange products of special orders

🟡 **L420** [技术债务]: this comes out as an amazing mess, but simplifies nicely

🟡 **L436** [技术债务]: this can be further simplified!

🟡 **L444** [技术债务]: more

🟡 **L466** [技术债务]: for this to work with real a, need to expand abs(a*x) to abs(a)*abs(x)

🟡 **L479** [技术债务]: IFT is a *mess*

🟡 **L481** [技术债务]: IFT

🟡 **L492** [技术债务]: IFT without factoring comes out as meijer g

🟡 **L502** [技术债务]: IFT (comes out as meijer G)

🟡 **L504** [技术债务]: besselj(n, x), n an integer > 0 actually can be done...

🟡 **L506** [技术债务]: are there other common transforms (no distributions!)?


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_manual.py

🟡 **L113** [技术债务]: equals returns None


### venv/lib/python3.13/site-packages/sympy/assumptions/predicates/matrices.py

🟡 **L70** [技术债务]: Add handlers to make these keys work with


### venv/lib/python3.13/site-packages/sympy/assumptions/predicates/calculus.py

🟡 **L57** [技术债务]: Add examples


### venv/lib/python3.13/site-packages/sympy/assumptions/predicates/common.py

🟡 **L17** [技术债务]: Add examples


### venv/lib/python3.13/site-packages/sympy/assumptions/predicates/sets.py

🟡 **L238** [技术债务]: Add examples

🟡 **L337** [技术债务]: Add examples

🟡 **L394** [技术债务]: Add examples


### venv/lib/python3.13/site-packages/sympy/assumptions/handlers/order.py

🟡 **L218** [技术债务]: This should be deducible from the nonzero handler


### venv/lib/python3.13/site-packages/sympy/plotting/backends/matplotlibbackend/matplotlib.py

🟡 **L240** [技术债务]: The 3D stuff


### venv/lib/python3.13/site-packages/sympy/sets/tests/test_setexpr.py

🟡 **L29** [技术债务]: add support for more functions in the future:

🟡 **L206** [技术债务]: some expressions cannot be calculated due to bugs (currently


### venv/lib/python3.13/site-packages/sympy/sets/tests/test_fancysets.py

🟡 **L152** [技术债务]: This doesn't yet work:


### venv/lib/python3.13/site-packages/sympy/sets/handlers/functions.py

🟡 **L38** [技术债务]: handle functions with infinitely many solutions (eg, sin, tan)

🟡 **L39** [技术债务]: handle multivariate functions


### venv/lib/python3.13/site-packages/sympy/sets/handlers/mul.py

🟡 **L34** [技术债务]: some intervals containing 0 and oo will fail as 0*oo returns nan.

🟡 **L41** [技术债务]: handle symbolic intervals


### venv/lib/python3.13/site-packages/sympy/sets/handlers/intersection.py

🟡 **L371** [技术债务]: Design a technique to handle multiple-inverse


### venv/lib/python3.13/site-packages/sympy/sets/handlers/power.py

🟡 **L46** [技术债务]: handle unevaluated condition.

🟡 **L49** [技术债务]: `s2 > s1` could be unevaluated.

🟡 **L85** [技术债务]: add logic for open intervals?


### venv/lib/python3.13/site-packages/sympy/interactive/tests/test_ipython.py

🟡 **L10** [技术债务]: The code below could be made more granular with something like:

🟡 **L74** [技术债务]: How can we test that the output of a SyntaxError is the original


### venv/lib/python3.13/site-packages/sympy/functions/special/spherical_harmonics.py

🟡 **L150** [技术债务]: Add more simplififcation here

🟡 **L179** [技术债务]: Make sure n \in N

🟡 **L180** [技术债务]: Assert |m| <= n ortherwise we should return 0

🟡 **L189** [技术债务]: Make sure n \in N

🟡 **L190** [技术债务]: Assert |m| <= n ortherwise we should return 0

🟡 **L197** [技术债务]: Make sure theta \in R and phi \in R

🟡 **L202** [技术债务]: Handle deep and hints


### venv/lib/python3.13/site-packages/sympy/functions/special/hyper.py

🟡 **L47** [技术债务]: should __new__ accept **options?

🟡 **L48** [技术债务]: should constructors should check if parameters are sensible?

🟡 **L210** [技术债务]: should we check convergence conditions?

🟡 **L543** [技术债务]: should we check convergence conditions?

🟡 **L980** [技术债务]: this can be nicer


### venv/lib/python3.13/site-packages/sympy/functions/special/gamma_functions.py

🟡 **L687** [技术债务]: n == 1 also can do some rational z


### venv/lib/python3.13/site-packages/sympy/functions/special/zeta_functions.py

🟡 **L150** [技术债务]: should something be polarified here?

🟡 **L181** [技术债务]: reference?


### venv/lib/python3.13/site-packages/sympy/functions/special/error_functions.py

🟡 **L24** [技术债务]: series expansions

🟡 **L25** [技术债务]: see the "Note:" in Ei

🟡 **L1220** [技术债务]: :

🟡 **L2738** [技术债务]: is the series really correct?


### venv/lib/python3.13/site-packages/sympy/functions/combinatorial/numbers.py

🟡 **L2758** [技术债务]: make this a class like bell()


### venv/lib/python3.13/site-packages/sympy/functions/combinatorial/factorials.py

🟡 **L423** [技术债务]: extend this to complex numbers?


### venv/lib/python3.13/site-packages/sympy/functions/elementary/trigonometric.py

🟡 **L499** [技术债务]: Do this more efficiently for more than two terms

🟡 **L867** [技术债务]: Do this more efficiently for more than two terms

🟡 **L1226** [技术债务]: currently tan(pi/2) return zoo

🟡 **L1579** [技术债务]: refactor into TrigonometricFunction common parts of


### venv/lib/python3.13/site-packages/sympy/functions/elementary/exponential.py

🟡 **L985** [技术债务]: new and probably slow


### venv/lib/python3.13/site-packages/sympy/functions/elementary/piecewise.py

🟡 **L456** [技术债务]: Currently complex intervals are not supported.  A possible

🟡 **L578** [技术债务]: simplify hi <= upto


### venv/lib/python3.13/site-packages/sympy/functions/special/tests/test_delta_functions.py

🟡 **L37** [技术债务]: this is generally undefined @ x=0


### venv/lib/python3.13/site-packages/sympy/functions/elementary/tests/test_piecewise.py

🟡 **L1223** [技术债务]: raise error if function is discontinuous at limit of


### venv/lib/python3.13/site-packages/sympy/functions/elementary/tests/test_complexes.py

🟡 **L938** [技术债务]: XXX why does abs(x)._eval_evalf() not fall back to global evalf?


### venv/lib/python3.13/site-packages/sympy/tensor/array/ndim_array.py

🟡 **L567** [技术债务]: add checks for dimensions for `value`?


### venv/lib/python3.13/site-packages/sympy/tensor/array/array_derivatives.py

🟡 **L91** [技术债务]: this could be done with multiple-dispatching:


### venv/lib/python3.13/site-packages/sympy/tensor/tests/test_tensor.py

🟡 **L497** [技术债务]: add check for *get_symmetric_group_sgs(0)


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/from_array_to_matrix.py

🟡 **L124** [技术债务]: is this break necessary?

🟡 **L297** [技术债务]: this assumes that all arguments are matrices, it may not be the case:

🟡 **L542** [技术债务]: move this to ElementwiseApplyFunction


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/from_indexed_to_array.py

🟡 **L113** [技术债务]: check that Kronecker delta is only contracted to one other element:


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/array_expressions.py

🟡 **L605** [技术债务]: swap args positions in order to simplify the expression:

🟡 **L606** [技术债务]: this should be in a function

🟡 **L641** [技术债务]: function in order to permute the args:

🟡 **L842** [技术债务]: add API for total rank and cumulative rank:

🟡 **L1263** [技术债务]: add API for total rank and cumulative rank:

🟡 **L1390** [技术债务]: check that `expr` has `.subranks`:


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/tests/test_array_expressions.py

🟡 **L50** [技术债务]: not yet supported:

🟡 **L54** [技术债务]: not yet supported:

🟡 **L445** [技术债务]: reverse operation starting with `PermuteDims` and getting down to `bb`...


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/tests/test_convert_array_to_matrix.py

🟡 **L189** [技术债务]: this is returning a wrong result:


### venv/lib/python3.13/site-packages/sympy/physics/hep/gamma_matrices.py

🟡 **L315** [技术债务]: specific for d=4


### venv/lib/python3.13/site-packages/sympy/physics/mechanics/kane.py

🟡 **L630** [技术债务]: : Remove `new_method` after 1.1 has been released.


### venv/lib/python3.13/site-packages/sympy/physics/units/dimensions.py

🟡 **L351** [技术债务]: should this raise a warning?

🟡 **L522** [技术债务]: the inversion will fail if the system is inconsistent, for


### venv/lib/python3.13/site-packages/sympy/physics/vector/vector.py

🟡 **L735** [技术债务]: : Circular dependency if imported at top. Should move


### venv/lib/python3.13/site-packages/sympy/physics/optics/gaussopt.py

🟡 **L885** [技术债务]: add the other possible arguments


### venv/lib/python3.13/site-packages/sympy/physics/quantum/trace.py

🟡 **L94** [技术债务]: Need to handle printing

🟡 **L172** [技术债务]: Current version ignores the indices set for partial trace.

🟡 **L192** [技术债务]: Review if the permute method is needed


### venv/lib/python3.13/site-packages/sympy/physics/quantum/cg.py

🟡 **L1** [技术债务]: :

🟡 **L675** [技术债务]: Check for symmetries


### venv/lib/python3.13/site-packages/sympy/physics/quantum/matrixutils.py

🟡 **L141** [技术债务]: Move this into sympy.matrices.


### venv/lib/python3.13/site-packages/sympy/physics/quantum/spin.py

🟡 **L145** [技术债务]: add methods for uncoupling operators

🟡 **L157** [技术债务]: move this to qapply_Mul

🟡 **L165** [技术债务]: use options to use different j values

🟡 **L1017** [技术债务]: better way to get angles of rotation


### venv/lib/python3.13/site-packages/sympy/physics/quantum/represent.py

🟡 **L417** [技术债务]: Add support for sets of operators


### venv/lib/python3.13/site-packages/sympy/physics/quantum/operator.py

🟡 **L428** [技术债务]: make sure the hilbert spaces of the bra and ket are

🟡 **L491** [技术债务]: if operands are tensorproducts this may be will be handled


### venv/lib/python3.13/site-packages/sympy/physics/quantum/tensorproduct.py

🟡 **L151** [技术债务]: disallow nested TensorProducts.


### venv/lib/python3.13/site-packages/sympy/physics/quantum/matrixcache.py

🟡 **L78** [技术债务]: explore different sparse formats. But sparse.kron will use


### venv/lib/python3.13/site-packages/sympy/physics/quantum/qapply.py

🟡 **L104** [技术债务]: don't expand the scalars in front of each Mul.

🟡 **L251** [技术债务]: I may need to expand before returning the final result.


### venv/lib/python3.13/site-packages/sympy/physics/mechanics/tests/test_particle.py

🟡 **L55** [技术债务]: make the result not be system-dependent


### venv/lib/python3.13/site-packages/sympy/physics/units/tests/test_quantities.py

🟡 **L206** [技术债务]: decide whether to allow such expression in the future

🟡 **L227** [技术债务]: Pow only support structural equality:

🟡 **L244** [技术债务]: need better simplification routine:

🟡 **L249** [技术债务]: need a better way to simplify expressions containing units:


### venv/lib/python3.13/site-packages/sympy/physics/vector/tests/test_printing.py

🟡 **L47** [技术债务]: : The unit vectors should print with subscripts but they just

🟡 **L50** [技术债务]: : The pretty print division does not print correctly here:


### venv/lib/python3.13/site-packages/sympy/physics/quantum/tests/test_cartesian.py

🟡 **L113** [技术债务]: Add tests for representations


### venv/lib/python3.13/site-packages/sympy/physics/quantum/tests/test_trace.py

🟡 **L82** [技术债务]: needed while testing reduced density operations, etc.


### venv/lib/python3.13/site-packages/sympy/physics/quantum/tests/test_density.py

🟡 **L269** [技术债务]: test for invalid arguments


### venv/lib/python3.13/site-packages/sympy/parsing/autolev/_listener_autolev_antlr.py

🟡 **L796** [技术债务]: Currently only works with symbols. Make it work for dynamicsymbols.

🟡 **L1269** [技术债务]: ** Parse block matrices


### venv/lib/python3.13/site-packages/sympy/parsing/fortran/fortran_parser.py

🟡 **L102** [技术债务]: Arithmetic Assignment

🟡 **L151** [技术债务]: Integer Binary Operations

🟡 **L239** [技术债务]: Numbers when the LFortran ASR is updated

🟡 **L257** [技术债务]: Return statement, variable declaration


### venv/lib/python3.13/site-packages/sympy/parsing/c/c_parser.py

🟡 **L520** [技术债务]: No string type in AST


### venv/lib/python3.13/site-packages/sympy/parsing/latex/lark/transformer.py

🟡 **L660** [技术债务]: ANTLR refers to ISO 80000-2:2019. should we keep base 10 or base 2?


### venv/lib/python3.13/site-packages/sympy/simplify/tests/test_hyperexpand.py

🟡 **L116** [技术债务]: [a+1, aRational(-1, 2)], [2*a]

🟡 **L130** [技术债务]: hyperexpand(hyper([a], [2*a + 1], z))

🟡 **L131** [技术债务]: [S.Half, a], [Rational(3, 2), a+1]

🟡 **L135** [技术债务]: [a], [a - S.Half, 2*a]

🟡 **L949** [技术债务]: polys

🟡 **L1011** [技术债务]: LOTS more

🟡 **L1039** [技术债务]: LOTS more


### venv/lib/python3.13/site-packages/sympy/diffgeom/tests/test_class_structure.py

🟡 **L19** [技术债务]: assert point.subs(x, 2) == Point(cs, [2, y])

🟡 **L20** [技术债务]: assert point.free_symbols == set([x, y])


### venv/lib/python3.13/site-packages/sympy/diffgeom/tests/test_diffgeom.py

🟡 **L103** [技术债务]: assert m == R2_r.transform(R2_p, R2_p.transform(R2_r, [a, b])).applyfunc(simplify)

🟡 **L117** [技术债务]: assert m == R3_r.transform(R3_c, R3_c.transform(R3_r, m)).applyfunc(simplify)

🟡 **L120** [技术债务]: assert m == R3_r.transform(R3_s, R3_s.transform(R3_r, m)).applyfunc(simplify)

🟡 **L123** [技术债务]: assert m == R3_c.transform(R3_s, R3_s.transform(R3_c, m)).applyfunc(simplify)

🟡 **L128** [技术债务]: assert m == R3_r.coord_tuple_transform_to(R3_c, R3_c.coord_tuple_transform_to(R3_r, m)).applyfunc(simplify)

🟡 **L131** [技术债务]: assert m == R3_r.coord_tuple_transform_to(R3_s, R3_s.coord_tuple_transform_to(R3_r, m)).applyfunc(simplify)

🟡 **L134** [技术债务]: assert m == R3_c.coord_tuple_transform_to(R3_s, R3_s.coord_tuple_transform_to(R3_c, m)).applyfunc(simplify)


### venv/lib/python3.13/site-packages/sympy/diffgeom/tests/test_hyperbolic_space.py

🟡 **L86** [技术债务]: - it would be nice to have index contraction built-in


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_finite_rv.py

🟡 **L68** [技术债务]: Make iid method!


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_continuous_rv.py

🟡 **L1290** [技术债务]: simplify(E(X)) seems to hang without extended_positive=True


### venv/lib/python3.13/site-packages/sympy/matrices/tests/test_commonmatrix.py

🟡 **L1167** [技术债务]: currently not working as ``_MinimalMatrix`` cannot be sympified:


### venv/lib/python3.13/site-packages/sympy/matrices/expressions/tests/test_derivatives.py

🟡 **L52** [技术债务]: this is commented because it slows down the tests.

🟡 **L105** [技术债务]: find a way to represent a four-dimensional zero-array:

🟡 **L225** [技术债务]: TensorProduct is not supported

🟡 **L292** [技术债务]: no support for TensorProduct.

🟡 **L407** [技术债务]: restore this result (currently returning the transpose):

🟡 **L416** [技术债务]: restore (currently returning the transpose):

🟡 **L444** [技术债务]: wrong

🟡 **L448** [技术债务]: wrong


### venv/lib/python3.13/site-packages/pygments/lexers/c_like.py

🟡 **L212** [技术债务]: "correctly" parse complex code attributes


### venv/lib/python3.13/site-packages/pygments/lexers/graphics.py

🟡 **L41** [技术债务]: when e is present, no decimal point needed

🟡 **L172** [技术债务]: when e is present, no decimal point needed


### venv/lib/python3.13/site-packages/pygments/lexers/ada.py

🟡 **L116** [技术债务]: use Name.Namespace if appropriate.  This needs


### venv/lib/python3.13/site-packages/pygments/lexers/objective.py

🟡 **L130** [技术债务]: unsure if ellipses are allowed elsewhere, see


### venv/lib/python3.13/site-packages/pygments/lexers/mojo.py

🟡 **L123** [技术债务]: varname the right fit?

🟡 **L273** [技术债务]: https://docs.modular.com/mojo/roadmap#no-async-for-or-async-with

🟡 **L274** [技术债务]: https://docs.modular.com/mojo/roadmap#no-async-for-or-async-with

🟡 **L702** [技术债务]: supported?


### venv/lib/python3.13/site-packages/pygments/lexers/inferno.py

🟡 **L85** [技术债务]: :


### venv/lib/python3.13/site-packages/pygments/lexers/nix.py

🟡 **L123** [技术债务]: we should probably escape also here ''${ \${

🟡 **L135** [技术债务]: let/in


### venv/lib/python3.13/site-packages/pygments/lexers/dns.py

🟡 **L53** [技术债务]: , $GENERATE https://bind9.readthedocs.io/en/v9.18.14/chapter3.html#soa-rr


### venv/lib/python3.13/site-packages/pygments/lexers/perl.py

🟡 **L35** [技术债务]: give this to a perl guy who knows how to parse perl...


### venv/lib/python3.13/site-packages/pygments/lexers/textfmts.py

🟡 **L240** [技术债务]: Make date regex more ISO 8601 compliant


### venv/lib/python3.13/site-packages/pygments/lexers/rnc.py

🟡 **L36** [技术债务]: single quoted strings and escape sequences outside of


### venv/lib/python3.13/site-packages/pygments/lexers/scripting.py

🟡 **L1524** [技术债务]: JES3 statement


### venv/lib/python3.13/site-packages/pygments/lexers/oberon.py

🟡 **L50** [技术债务]: nested comments (* (* ... *) ... (* ... *) *) not supported!


### venv/lib/python3.13/site-packages/pygments/lexers/markup.py

🟡 **L536** [技术债务]: aren't the offsets wrong?

🟡 **L672** [技术债务]: language-dependent syntax highlighting (see Markdown lexer)

🟡 **L698** [技术债务]: token

🟡 **L1003** [技术债务]: Use ABC lexer in the future


### venv/lib/python3.13/site-packages/pygments/lexers/templates.py

🟡 **L755** [技术债务]: support other Python syntax like $foo['bar']

🟡 **L1403** [技术债务]: I want to make these keywords but still parse attributes.


### venv/lib/python3.13/site-packages/pygments/lexers/css.py

🟡 **L593** [技术债务]: It's not currently possible to simply do the following,


### venv/lib/python3.13/site-packages/pygments/lexers/typst.py

🟡 **L135** [技术债务]: make this work


### venv/lib/python3.13/site-packages/pygments/lexers/textedit.py

🟡 **L140** [技术债务]: regexes can have other delims

🟡 **L191** [技术债务]: builtins are only subsequent tokens on lines


### venv/lib/python3.13/site-packages/pygments/lexers/mips.py

🟡 **L28** [技术债务]: add '*.s' and '*.asm', which will require designing an analyse_text


### venv/lib/python3.13/site-packages/pygments/lexers/meson.py

🟡 **L27** [技术债务]: String interpolation @VARNAME@ inner matches

🟡 **L28** [技术债务]: keyword_arg: value inner matches


### venv/lib/python3.13/site-packages/pygments/lexers/jvm.py

🟡 **L891** [技术债务]: / should divide keywords/symbols into namespace/rest

🟡 **L1346** [技术债务]: make tests pass without \s+


### venv/lib/python3.13/site-packages/pygments/lexers/sql.py

🟡 **L150** [技术债务]: better logging

🟡 **L223** [技术债务]: use inheritance

🟡 **L347** [技术债务]: better handle multiline comments at the end with

🟡 **L590** [技术债务]: Backslash escapes?


### venv/lib/python3.13/site-packages/pygments/lexers/haskell.py

🟡 **L446** [技术债务]: these don't match the comments in docs, remove.


### venv/lib/python3.13/site-packages/pygments/lexers/javascript.py

🟡 **L133** [技术债务]: should this include single-line comments and allow nesting strings?


### venv/lib/python3.13/site-packages/pygments/lexers/julia.py

🟡 **L195** [技术债务]: This escape pattern is not perfect.


### venv/lib/python3.13/site-packages/pygments/lexers/dotnet.py

🟡 **L558** [技术债务]: support multiple languages within the same source file


### venv/lib/python3.13/site-packages/pygments/lexers/fantom.py

🟡 **L49** [技术债务]: highlight references in fandocs

🟡 **L85** [技术债务]: remove copy/paste str/uri


### venv/lib/python3.13/site-packages/pygments/lexers/wgsl.py

🟡 **L390** [技术债务]: Treat context-depedendent names specially

🟡 **L396** [技术债务]: templates start and end tokens.


### venv/lib/python3.13/site-packages/pygments/formatters/img.py

🟡 **L548** [技术债务]: make sure tab expansion happens earlier in the chain.  It


### venv/lib/python3.13/site-packages/pygments/formatters/terminal256.py

🟡 **L17** [技术债务]: :


### venv/lib/python3.13/site-packages/pygments/formatters/latex.py

🟡 **L334** [技术债务]: add support for background colors


### venv/lib/python3.13/site-packages/grpc/beta/_server_adaptations.py

🟡 **L405** [技术债务]: (nathaniel): call the multimethod.


### venv/lib/python3.13/site-packages/grpc/aio/_metadata.py

🟡 **L68** [技术债务]: (asheshvidyut): Make this method public and encourage people to use it instead


### venv/lib/python3.13/site-packages/mpmath/libmp/libintmath.py

🟡 **L129** [技术债务]: speed up for bases 2, 4, 8, 16, ...


### venv/lib/python3.13/site-packages/mpmath/libmp/libhyper.py

🟡 **L199** [技术债务]: when there are several real parameters and just a few complex

🟡 **L332** [技术债务]: mpf_erf should call mpf_erfc when appropriate (currently

🟡 **L355** [技术债务]: interval rounding

🟡 **L617** [技术债务]: could return finite imaginary value at -inf

🟡 **L911** [技术债务]: for extremely large x, we could use an asymptotic

🟡 **L1081** [技术债务]: for |x| << 1/2, one could use fall back to


### venv/lib/python3.13/site-packages/mpmath/libmp/libelefun.py

🟡 **L342** [技术债务]: handle rnd direction of the logarithm carefully

🟡 **L711** [技术债务]: if close enough to 1, we could use Taylor series

🟡 **L876** [技术债务]: cleanup the special cases

🟡 **L1158** [技术债务]: the best cutoff depends on both x and the precision.


### venv/lib/python3.13/site-packages/mpmath/libmp/libmpf.py

🟡 **L1175** [技术债务]: account for precision when doing this


### venv/lib/python3.13/site-packages/mpmath/libmp/libmpc.py

🟡 **L498** [技术债务]: handle cancellation when c ~=  -1 and ch ~= 1

🟡 **L584** [技术债务]: avoid loss of accuracy


### venv/lib/python3.13/site-packages/mpmath/libmp/libmpi.py

🟡 **L367** [技术债务]: combine evaluation code to avoid duplicate modulo

🟡 **L670** [技术债务]: accuracy for small x

🟡 **L759** [技术债务]: recognize/speed up real cases, integer y

🟡 **L848** [技术债务]: reflection formula

🟡 **L885** [技术债务]: reflection formula


### venv/lib/python3.13/site-packages/mpmath/tests/test_linalg.py

🟡 **L1** [技术债务]: don't use round


### venv/lib/python3.13/site-packages/mpmath/tests/test_matrices.py

🟡 **L57** [技术债务]: remove exec() wrapper as soon as we drop support for Python <= 3.5


### venv/lib/python3.13/site-packages/mpmath/tests/test_interval.py

🟡 **L273** [技术债务]: many more tests

🟡 **L378** [技术债务]: error_dps should not be necessary

🟡 **L404** [技术债务]: need many more tests


### venv/lib/python3.13/site-packages/mpmath/tests/test_gammazeta.py

🟡 **L599** [技术债务]: more tests for polyexp


### venv/lib/python3.13/site-packages/mpmath/tests/runtests.py

🟡 **L57** [技术债务]: add a flag for this


### venv/lib/python3.13/site-packages/mpmath/functions/zeta.py

🟡 **L287** [技术债务]: for bernpoly and eulerpoly, ensure that all exact zeros are covered

🟡 **L697** [技术债务]: the following could perhaps be tidied a bit


### venv/lib/python3.13/site-packages/mpmath/functions/functions.py

🟡 **L182** [技术债务]: accurately eval the smaller of the real/imag parts

🟡 **L212** [技术债务]: accurately eval the smaller of the real/imag part

🟡 **L257** [技术债务]: this can be done *much* faster

🟡 **L604** [技术债务]: the following could be generalized into a perfect


### venv/lib/python3.13/site-packages/mpmath/functions/hypergeometric.py

🟡 **L284** [技术债务]: handle the all-real case more efficiently!

🟡 **L285** [技术债务]: figure out how much precision is needed (exponential growth)

🟡 **L404** [技术债务]: the following logic can be simplified

🟡 **L760** [技术债务]: much of the following could be shared with 2F3 instead of

🟡 **L832** [技术债务]: much of the following could be shared with 2F3 instead of

🟡 **L1091** [技术债务]: continuation

🟡 **L1107** [技术债务]: continuation


### venv/lib/python3.13/site-packages/mpmath/functions/orthogonal.py

🟡 **L18** [技术债务]: :

🟡 **L313** [技术债务]: something else is required here

🟡 **L373** [技术债务]: correct evaluation at singularities


### venv/lib/python3.13/site-packages/mpmath/functions/expintegrals.py

🟡 **L265** [技术债务]: reasonable sign of infinity


### venv/lib/python3.13/site-packages/mpmath/functions/bessel.py

🟡 **L28** [技术债务]: the integer special-casing shouldn't be necessary.

🟡 **L147** [技术债务]: avoid cancellation for imaginary arguments

🟡 **L384** [技术债务]: do this more generically?

🟡 **L423** [技术债务]: could be expressed more elegantly using triple factorials

🟡 **L468** [技术债务]: limits

🟡 **L521** [技术债务]: asymptotic series for derivatives

🟡 **L562** [技术债务]: limits

🟡 **L718** [技术债务]: check that chop=True chops when and only when it should

🟡 **L757** [技术债务]: check that chop=True chops when and only when it should

🟡 **L878** [技术债务]: use v <= j'_{v,1} < y_{v,1}?


### venv/lib/python3.13/site-packages/mpmath/calculus/optimization.py

🟡 **L264** [技术债务]: maybe refactoring with function for divided differences

🟡 **L289** [技术债务]: consider raising a ValueError when there's no sign change in a and b

🟡 **L418** [技术债务]: better condition (when f is very flat)

🟡 **L457** [技术债务]: check whether it's possible to combine it with Illinois stuff

🟡 **L503** [技术债务]: better condition (when f is very flat)

🟡 **L560** [技术债务]: decide not to use convergence acceleration

🟡 **L573** [技术债务]: add Brent

🟡 **L601** [技术债务]: test with user-specified jacobian matrix

🟡 **L984** [技术债务]: better condition?


### venv/lib/python3.13/site-packages/mpmath/calculus/extrapolation.py

🟡 **L1969** [技术债务]: we are evaluating log(1+eps) -> eps, which is


### venv/lib/python3.13/site-packages/mpmath/matrices/matrices.py

🟡 **L4** [技术债务]: interpret list as vectors (for multiplication)


### venv/lib/python3.13/site-packages/mpmath/matrices/calculus.py

🟡 **L3** [技术债务]: should use diagonalization-based algorithms


### venv/lib/python3.13/site-packages/mpmath/matrices/linalg.py

🟡 **L99** [技术债务]: :

🟡 **L136** [技术债务]: what if equal?

🟡 **L218** [技术债务]: necessary to check also b?

🟡 **L239** [技术债务]: really?


### venv/lib/python3.13/site-packages/mpmath/matrices/eigen_symmetric.py

🟡 **L8** [技术债务]: :


### venv/lib/python3.13/site-packages/mpmath/matrices/eigen.py

🟡 **L8** [技术债务]: :


### venv/lib/python3.13/site-packages/redis/asyncio/client.py

🟡 **L1440** [技术债务]: (next-major): when the async Connection.read_response


### venv/lib/python3.13/site-packages/redis/asyncio/connection.py

🟡 **L1232** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L1268** [技术债务]: (next-major): drop the math.inf branch. Use SENTINEL as the


### venv/lib/python3.13/site-packages/redis/asyncio/cluster.py

🟡 **L2097** [技术债务]: Make this method async in the next major release to allow


### venv/lib/python3.13/site-packages/redis/asyncio/lock.py

🟡 **L256** [技术债务]: this can be simplified when the context manager is finished


### venv/lib/python3.13/site-packages/redis/_parsers/hiredis.py

🟡 **L160** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L322** [技术债务]: Rename this API; it detects pending data or dirty/closed


### venv/lib/python3.13/site-packages/redis/_parsers/base.py

🟡 **L165** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L190** [技术债务]: Rename this API; it detects pending data or dirty/closed

🟡 **L546** [技术债务]: Rename this API; it detects pending data or dirty/closed


### venv/lib/python3.13/site-packages/redis/commands/json/__init__.py

🟡 **L349** [技术债务]: rsplit(".") splits on all dots, mishandling paths


### venv/lib/python3.13/site-packages/redis/commands/json/commands.py

🟡 **L707** [技术债务]: rsplit(".") splits on all dots, mishandling paths


### venv/lib/python3.13/site-packages/cryptography/x509/name.py

🟡 **L368** [技术债务]: this is relatively expensive, if this looks like a bottleneck


### venv/lib/python3.13/site-packages/cryptography/hazmat/asn1/asn1.py

🟡 **L82** [技术债务]: Drop the `hasattr()` once the minimum supported Python version

🟡 **L515** [技术债务]: replace with `Default[U]` once the min Python version is >= 3.12


### venv/lib/python3.13/site-packages/opentelemetry/context/__init__.py

🟡 **L140** [技术债务]: This is a temporary location for the suppress instrumentation key.


### venv/lib/python3.13/site-packages/opentelemetry/sdk/util/instrumentation.py

🟡 **L10** [技术债务]: see if we can remove F401 when using new sphinx version # noqa: F401 # pylint: disable=unused-import


### venv/lib/python3.13/site-packages/opentelemetry/sdk/_shared_internal/__init__.py

🟡 **L101** [技术债务]: (https://github.com/open-telemetry/opentelemetry-python/issues/4555): figure out what this should do.


### venv/lib/python3.13/site-packages/opentelemetry/sdk/metrics/_internal/aggregation.py

🟡 **L885** [技术债务]: Find the right value for flags

🟡 **L1061** [技术债务]: Find the right value for flags


### venv/lib/python3.13/site-packages/opentelemetry/sdk/metrics/_internal/__init__.py

🟡 **L140** [技术债务]: #2558 go through all views here and check if this

🟡 **L173** [技术债务]: #2558 go through all views here and check if this

🟡 **L216** [技术债务]: #2558 go through all views here and check if this

🟡 **L280** [技术债务]: #2558 go through all views here and check if this

🟡 **L307** [技术债务]: #2558 go through all views here and check if this

🟡 **L346** [技术债务]: #2558 go through all views here and check if this

🟡 **L385** [技术债务]: #2558 go through all views here and check if this

🟡 **L694** [技术债务]: #2558 pass SDKConfig object to meter so that the meter


### venv/lib/python3.13/site-packages/IPython/core/async_helpers.py

🟡 **L132** [技术债务]: do not raise but return an execution result with the right info.


### venv/lib/python3.13/site-packages/IPython/core/completerlib.py

🟡 **L36** [技术债务]: this should be pulled in with the right call via the component system

🟡 **L283** [技术债务]: there's a lot of logic common to the run, cd and builtin file


### venv/lib/python3.13/site-packages/IPython/core/tbtools.py

🟡 **L512** [技术债务]: emit deprecation


### venv/lib/python3.13/site-packages/IPython/core/guarded_eval.py

🟡 **L872** [技术债务]: support class decorators?

🟡 **L982** [技术债务]: populate transient_locals


### venv/lib/python3.13/site-packages/IPython/core/display_functions.py

🟡 **L68** [技术债务]: We could check for ipykernel version and provide a detailed upgrade message.


### venv/lib/python3.13/site-packages/IPython/core/doctb.py

🟡 **L102** [技术债务]: no default ?


### venv/lib/python3.13/site-packages/IPython/core/logger.py

🟡 **L30** [技术债务]: This class isn't a mixin anymore, but it still needs attributes from


### venv/lib/python3.13/site-packages/IPython/core/completer.py

🟡 **L1401** [技术债务]: make this faster by reusing parts of the computation?

🟡 **L2202** [技术债务]: add a heuristic for suppressing (e.g. if it has OS-specific delimiter,

🟡 **L2834** [技术债务]: maybe distinguish between functions, modules and just "variables"

🟡 **L3440** [技术债务]: :

🟡 **L3524** [技术债务]: Q: does the above refer to jedi completions (i.e. 0-indexed?)

🟡 **L3525** [技术债务]: should we deprecate now, or does it stay?

🟡 **L3535** [技术债务]: can we confirm that excluding Jedi here was a deliberate choice in previous version?

🟡 **L3727** [技术债务]: Jedi completions non included in legacy stateful API; was this deliberate or omission?

🟡 **L3760** [技术债务]: use `context.limit` to terminate early once we matched the maximum

🟡 **L3784** [技术债务]: self.unicode_names is here a list we traverse each time with ~100k elements.


### venv/lib/python3.13/site-packages/IPython/core/ultratb.py

🟡 **L499** [技术债务]: no default ?

🟡 **L1092** [技术债务]: no default

🟡 **L1246** [技术债务]: we should remove the auto pdb behavior from here and leave


### venv/lib/python3.13/site-packages/IPython/core/debugger.py

🟡 **L784** [技术债务]: investigate Toke.Line here, likely LineEm,

🟡 **L795** [技术债务]: investigate Toke.Line here, likely Line

🟡 **L860** [技术债务]: investigate Token.Line here


### venv/lib/python3.13/site-packages/IPython/core/interactiveshell.py

🟡 **L584** [技术债务]: this part of prompt management should be moved to the frontends.

🟡 **L652** [技术债务]: When we override sys.stdout and sys.stderr before this class

🟡 **L678** [技术债务]: init_io() needs to happen before init_traceback handlers

🟡 **L1265** [技术债务]: . For some strange reason, __builtins__ is showing up at user

🟡 **L1898** [技术债务]: only apply format_screen to the plain/text repr of the mime

🟡 **L2453** [技术债务]: magic aliases should be defined by the Magics classes

🟡 **L2462** [技术债务]: Move the color initialization to the DisplayHook, which


### venv/lib/python3.13/site-packages/IPython/core/displayhook.py

🟡 **L20** [技术债务]: Move the various attributes (cache_size, [others now moved]). Some

🟡 **L328** [技术债务]: Is this really needed?


### venv/lib/python3.13/site-packages/IPython/sphinxext/ipython_directive.py

🟡 **L1028** [技术债务]: , any reason block_parser can't be a method of embeddable shell


### venv/lib/python3.13/site-packages/IPython/terminal/ptutils.py

🟡 **L166** [技术债务]: Use Jedi to determine meta_text


### venv/lib/python3.13/site-packages/IPython/terminal/interactiveshell.py

🟡 **L361** [技术债务]: deprecate this


### venv/lib/python3.13/site-packages/IPython/utils/PyColorize.py

🟡 **L479** [技术债务]: :


### venv/lib/python3.13/site-packages/IPython/testing/tools.py

🟡 **L199** [技术债务]: ignore all warnings in ipexec while we have shims


### venv/lib/python3.13/site-packages/IPython/testing/decorators.py

🟡 **L132** [技术债务]: should this be finnally ?


### venv/lib/python3.13/site-packages/IPython/lib/pretty.py

🟡 **L328** [技术债务]: try to construct a more thorough MRO.


### venv/lib/python3.13/site-packages/IPython/core/magics/execution.py

🟡 **L308** [技术债务]: port to magic_arguments as currently this is duplicated in IPCompleter._extract_code

🟡 **L1140** [技术债务]: port to magic_arguments as currently this is duplicated in IPCompleter._extract_code


### venv/lib/python3.13/site-packages/IPython/core/magics/packaging.py

🟡 **L25** [技术债务]: does this need to change on windows?


### venv/lib/python3.13/site-packages/IPython/testing/plugin/pytest_ipdoctest.py

🟡 **L381** [技术债务]: Type ignored -- breaks Liskov Substitution.

🟡 **L409** [技术债务]: ReprFileLocation doesn't expect a None lineno.


### venv/lib/python3.13/site-packages/seaborn/_core/subplots.py

🟡 **L11** [技术债务]: move to seaborn._core.typing?

🟡 **L34** [技术债务]: define as TypedDict

🟡 **L76** [技术债务]: what err class? Define PlotSpecError?

🟡 **L150** [技术债务]: reduce need to pass pair_spec here?

🟡 **L257** [技术债务]: TypedDict?


### venv/lib/python3.13/site-packages/seaborn/_core/moves.py

🟡 **L101** [技术债务]: accept just a str here?

🟡 **L102** [技术债务]: should this always be present?

🟡 **L103** [技术债务]: should the default be an "all" singleton?

🟡 **L120** [技术债务]: what value to fill missing widths??? Hard problem...

🟡 **L121** [技术债务]: short circuit this if outer widths has no variance?

🟡 **L163** [技术债务]: center? (or should this be a different move, eg. Stream())

🟡 **L167** [技术债务]: should stack do something with ymin/ymax style marks?

🟡 **L187** [技术债务]: where to ensure that other semantic variables are sorted properly?

🟡 **L188** [技术债务]: why are we not using the passed in groupby here?


### venv/lib/python3.13/site-packages/seaborn/_core/plot.py

🟡 **L61** [技术债务]: allow list?

🟡 **L62** [技术债务]: allow list?

🟡 **L97** [技术债务]: how to allow this to reflect the color cycle when relevant?

🟡 **L399** [技术债务]: any way to enforce that data does not get mutated?

🟡 **L534** [技术债务]: This API for transforms was a late decision, and previously Plot.add

🟡 **L567** [技术债务]: it doesn't work to supply scalars to variables, but it should

🟡 **L604** [技术债务]: Add transpose= arg, which would then draw pair(y=[...]) across rows

🟡 **L701** [技术债务]: def twin()?

🟡 **L844** [技术债务]: add an "auto" mode for figsize that roughly scales with the rcParams

🟡 **L860** [技术债务]: def legend (ugh)

🟡 **L902** [技术债务]: expose important keyword arguments in our signature?

🟡 **L919** [技术债务]: make pyplot configurable at the class level, and when not using,

🟡 **L936** [技术债务]: if we have _target object, pyplot should be determined by whether it

🟡 **L955** [技术债务]: Remove these after updating other methods

🟡 **L981** [技术债务]: decide if we ever want these (Plot.plot(debug=True))?

🟡 **L995** [技术债务]: type args

🟡 **L1012** [技术债务]: if we did not create the Plotter with pyplot, is it possible to do this?

🟡 **L1018** [技术债务]: API for accessing the underlying matplotlib objects

🟡 **L1019** [技术债务]: what else is useful in the public API for this class?

🟡 **L1023** [技术债务]: use matplotlib backend directly instead of going through savefig?

🟡 **L1025** [技术债务]: perhaps have self.show() flip a switch to disable this, so that

🟡 **L1028** [技术债务]: use bbox_inches="tight" like the inline backend?

🟡 **L1040** [技术债务]: put dpi in Plot.config?

🟡 **L1042** [技术债务]: _theme_with_defaults?

🟡 **L1055** [技术债务]: DPI for rasterized artists?

🟡 **L1060** [技术债务]: _theme_with_defaults?

🟡 **L1139** [技术债务]: Should we make it possible to use only one x/y label for

🟡 **L1153** [技术债务]: there should be some override (in Plot.layout?) so that

🟡 **L1180** [技术债务]: we want right-side titles for row facets in most cases?

🟡 **L1198** [技术债务]: or has_row and sub["right"] and <right titles>

🟡 **L1199** [技术债务]: and not <right titles>

🟡 **L1233** [技术债务]: to simplify typing

🟡 **L1357** [技术债务]: this implies that the variable was added by the stat

🟡 **L1423** [技术债务]: where best to define?

🟡 **L1436** [技术债务]: This is tricky, make sure we add some tests for this

🟡 **L1452** [技术债务]: what default?

🟡 **L1458** [技术债务]: what marks should have this?

🟡 **L1464** [技术债务]: unlike width, we might not want to add baseline to data

🟡 **L1490** [技术债务]: is this the right place for this?

🟡 **L1500** [技术债务]: do we still have numbers in the variable name at this point?

🟡 **L1515** [技术债务]: see https://github.com/matplotlib/matplotlib/issues/22713

🟡 **L1527** [技术债务]: retype return with subplot_spec or similar

🟡 **L1576** [技术债务]: note redundancies with preceding function ... needs refactoring

🟡 **L1648** [技术债务]: (from initial work on categorical plots refactor)

🟡 **L1661** [技术债务]: need copy(deep=...) policy (here, above, anywhere else?)

🟡 **L1799** [技术债务]: when would it not be?

🟡 **L1808** [技术债务]: switch default to "constrained"?

🟡 **L1809** [技术债务]: either way, make configurable


### venv/lib/python3.13/site-packages/seaborn/_core/properties.py

🟡 **L74** [技术债务]: put these somewhere external for validation

🟡 **L75** [技术债务]: putting this here won't pick it up if subclasses define infer_scale

🟡 **L82** [技术债务]: validate numeric type? That should happen centrally somewhere

🟡 **L128** [技术债务]: look into custom PlotSpecWarning with better formatting

🟡 **L174** [技术债务]: infer continuous based on log/sqrt etc?

🟡 **L186** [技术债务]: other variable types

🟡 **L272** [技术债务]: use rcparams?

🟡 **L309** [技术债务]: validate / enforce that output is in [0, 1]

🟡 **L398** [技术债务]: should we have named marker "palettes"? (e.g. see d3 options)

🟡 **L400** [技术债务]: need some sort of "require_scale" functionality

🟡 **L587** [技术债务]: when inferring Continuous without data, verify type

🟡 **L589** [技术债务]: need to rethink the variable type system

🟡 **L601** [技术债务]: It seems reasonable to allow a gradient mapping for nominal

🟡 **L610** [技术债务]: Do we accept str like "log", "pow", etc. for semantics?

🟡 **L629** [技术债务]: what is best way to do this conditional?

🟡 **L637** [技术债务]: Rethink best default continuous color gradient

🟡 **L640** [技术债务]: blend_palette will strip alpha, but we should support

🟡 **L644** [技术债务]: for matplotlib colormaps this will clip extremes, which is

🟡 **L660** [技术债务]: this will need to be more flexible to support RGBA tuples (see above)

🟡 **L755** [技术债务]: fire in a "nice" way (see above)

🟡 **L799** [技术债务]: turn this into a property registry with hooks, etc.

🟡 **L830** [技术债务]: pattern?

🟡 **L831** [技术债务]: gradient?


### venv/lib/python3.13/site-packages/seaborn/_core/scales.py

🟡 **L50** [技术债务]: Reverting typing to Any as it was proving too complicated to

🟡 **L119** [技术债务]: sometimes we need to handle scalars (e.g. for Line)

🟡 **L175** [技术债务]: this doesn't actually need to be a closure

🟡 **L263** [技术债务]: flexibility over format() which isn't great for numbers / dates

🟡 **L268** [技术债务]: move to Nominal._get_scale?

🟡 **L269** [技术债务]: this needs some more complicated rethinking about how to pass

🟡 **L292** [技术债务]: Currently just used in non-Coordinate contexts, but should

🟡 **L299** [技术债务]: array cast necessary to handle float/int mixture, which we need

🟡 **L304** [技术债务]: define this more centrally

🟡 **L306** [技术债务]: only do this with explicit order?

🟡 **L308** [技术债务]: isin fails when units_seed mixes numbers and strings (numpy error?)

🟡 **L470** [技术债务]: How to allow disabling of legend for all uses of property?

🟡 **L533** [技术债务]: Add this to deal with outliers?

🟡 **L766** [技术债务]: date: bool?

🟡 **L862** [技术债务]: ideally we would have concise coordinate ticks,

🟡 **L874** [技术债务]: Have this separate from Temporal or have Temporal(date=True) or similar?

🟡 **L877** [技术债务]: Needed? Or handle this at layer (in stat or as param, eg binning=)

🟡 **L880** [技术债务]: any need for color-specific scales?

🟡 **L922** [技术债务]: do we want to distinguish view/data intervals? e.g. for a legend

🟡 **L934** [技术债务]: how to do this in a configurable / auto way?


### venv/lib/python3.13/site-packages/seaborn/_core/rules.py

🟡 **L25** [技术债务]: VarType is an awfully overloaded name, but so is DataType ...

🟡 **L26** [技术债务]: adding unknown because we are using this in for scales, is that right?


### venv/lib/python3.13/site-packages/seaborn/_core/typing.py

🟡 **L7** [技术债务]: use ArrayLike?

🟡 **L26** [技术债务]: technically str is iterable

🟡 **L29** [技术债务]: for discrete mappings, it would be ideal to use a parameterized type


### venv/lib/python3.13/site-packages/seaborn/_core/data.py

🟡 **L90** [技术债务]: allow `data` to be a function (that is called on the source data?)

🟡 **L264** [技术债务]: Note: this fails when variable specs *only* have scalars!


### venv/lib/python3.13/site-packages/seaborn/_marks/line.py

🟡 **L252** [技术债务]: better checks on what variables we have

🟡 **L253** [技术债务]: what if only one exist?


### venv/lib/python3.13/site-packages/seaborn/_marks/bar.py

🟡 **L91** [技术债务]: Is inplace mod a problem?

🟡 **L99** [技术债务]: return some sensible default?

🟡 **L133** [技术债务]: no Property yet

🟡 **L136** [技术债务]: *is* this mappable?

🟡 **L200** [技术债务]: no Property yet

🟡 **L203** [技术债务]: *is* this mappable?


### venv/lib/python3.13/site-packages/seaborn/_marks/dot.py

🟡 **L64** [技术债务]: Not backcompat with allowed (but nonfunctional) univariate plots

🟡 **L122** [技术债务]: rcParam?

🟡 **L123** [技术债务]: rcParam?

🟡 **L129** [技术债务]: rcParam?

🟡 **L151** [技术债务]: handle this in resolve_color

🟡 **L175** [技术债务]: retype marker as MappableMarker

🟡 **L177** [技术债务]: rcParam?

🟡 **L178** [技术债务]: rcParam?

🟡 **L180** [技术债务]: auto alpha?

🟡 **L197** [技术债务]: Is inplace mod a problem?


### venv/lib/python3.13/site-packages/seaborn/_marks/area.py

🟡 **L35** [技术债务]: should really move this logic into resolve_color

🟡 **L112** [技术债务]: should this be settable / mappable?

🟡 **L121** [技术债务]: copying a lot of code from Bar, let's abstract this

🟡 **L164** [技术债务]: assert that all(ymax >= ymin)?

🟡 **L165** [技术债务]: what if only one exist?


### venv/lib/python3.13/site-packages/seaborn/_marks/base.py

🟡 **L95** [技术债务]: where is the right place to put this kind of type aliasing?

🟡 **L119** [技术债务]: does it make sense to have variation within a Mark's

🟡 **L126** [技术债务]: make this method private? Would extender every need to call directly?

🟡 **L160** [技术债务]: how does width *scaling* work, e.g. for violin width by count?

🟡 **L174** [技术债务]: Might this obviate the identity scale? Just don't add a scale?

🟡 **L189** [技术债务]: add source_func or similar to transform the source value?

🟡 **L200** [技术债务]: type scales

🟡 **L202** [技术债务]: The original version of this (in seaborn._base) did more checking.

🟡 **L205** [技术债务]: rethink this to map from scale type to "DV priority" and use that?

🟡 **L277** [技术债务]: First clause only needed to handle non-rgba arrays,


### venv/lib/python3.13/site-packages/seaborn/_stats/regression.py

🟡 **L27** [技术债务]: warn?

🟡 **L36** [技术债务]: we should have a way of identifying the method that will be applied


### venv/lib/python3.13/site-packages/seaborn/_stats/counting.py

🟡 **L139** [技术债务]: warning or cap on too many bins?

🟡 **L148** [技术债务]: We'll want this for ordinal / discrete scales too


### venv/lib/python3.13/site-packages/seaborn/_stats/density.py

🟡 **L112** [技术债务]: need to handle singular data


### venv/lib/python3.13/site-packages/seaborn/_stats/base.py

🟡 **L27** [技术债务]: consider whether this should be a parameter. Motivating example:


### venv/lib/python3.13/site-packages/fsspec/implementations/tar.py

🟡 **L93** [技术债务]: load and set saved index, if exists

🟡 **L105** [技术债务]: save index to self.index_store here, if set


### venv/lib/python3.13/site-packages/fsspec/implementations/local.py

🟡 **L359** [技术债务]: if all incoming paths were posix-compliant then separator would

🟡 **L400** [技术债务]: check if path is writable?


### venv/lib/python3.13/site-packages/fsspec/implementations/smb.py

🟡 **L394** [技术债务]: use transaction support in SMB protocol


### venv/lib/python3.13/site-packages/fsspec/implementations/http_sync.py

🟡 **L105** [技术债务]: encoding from headers

🟡 **L889** [技术债务]: not allowed in JS

🟡 **L902** [技术债务]: :


### venv/lib/python3.13/site-packages/fsspec/implementations/cached.py

🟡 **L341** [技术债务]: action where partial file exists in read-only cache


### venv/lib/python3.13/site-packages/fsspec/implementations/cache_metadata.py

🟡 **L143** [技术债务]: consolidate blocks here


### venv/lib/python3.13/site-packages/fsspec/implementations/http.py

🟡 **L108** [技术债务]: Maybe rename `self.kwargs` to `self.request_options` to make


### venv/lib/python3.13/site-packages/fsspec/implementations/reference.py

🟡 **L151** [技术债务]: derive fs from `root`

🟡 **L482** [技术债务]: only save needed columns

🟡 **L555** [技术债务]: only clear those that we wrote to?

🟡 **L762** [技术债务]: warning here, since this can be very expensive?

🟡 **L898** [技术债务]: if references is lazy, pre-fetch all paths in batch before access

🟡 **L999** [技术债务]: we make dircache by iterating over all entries, but for Spec >= 1,


### venv/lib/python3.13/site-packages/llvmlite/ir/types.py

🟡 **L9** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L478** [技术债务]: why does this not take self.element/self.count into account?


### venv/lib/python3.13/site-packages/llvmlite/tests/test_refprune.py

🟡 **L8** [技术债务]: : Get rid of Legacy tests once completely transitioned to NewPassManager

🟡 **L10** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L262** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L272** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L300** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L310** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L342** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L352** [技术债务]: Remove `else' once TP are no longer supported.


### venv/lib/python3.13/site-packages/llvmlite/tests/test_ir.py

🟡 **L16** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L126** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L149** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L175** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L287** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L405** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L626** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1044** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1087** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1113** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1140** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1160** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1170** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1232** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1281** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1322** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1385** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1508** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1539** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1631** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1661** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2349** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2434** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2443** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2455** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2754** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2769** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2787** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2822** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2851** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2861** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L2893** [技术债务]: Remove `else' once TP are no longer supported.


### venv/lib/python3.13/site-packages/llvmlite/tests/test_binding.py

🟡 **L21** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L1650** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1844** [技术债务]: Remove `else' once TP are no longer supported.

🟡 **L1953** [技术债务]: Remove `else' once TP are no longer supported.


### venv/lib/python3.13/site-packages/llvmlite/binding/targets.py

🟡 **L10** [技术债务]: Remove `opaque_pointers_enabled` once typed pointers are no longer

🟡 **L443** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L448** [技术债务]: Remove me once typed pointers are no longer supported.


### venv/lib/python3.13/site-packages/llvmlite/binding/context.py

🟡 **L3** [技术债务]: Remove me once typed pointers are no longer supported.

🟡 **L31** [技术债务]: Remove argtypes once typed pointers are no longer supported.

🟡 **L35** [技术债务]: Remove argtypes once typed pointers are no longer supported.


### venv/lib/python3.13/site-packages/xgboost/dask/__init__.py

🟡 **L154** [技术债务]: s:

🟡 **L2125** [技术债务]: (trivialfis): arguments differ due to additional parameters like group and


### venv/lib/python3.13/site-packages/xgboost/spark/core.py

🟡 **L185** [技术债务]: supply hint message for all other unsupported params.

🟡 **L707** [技术债务]: support "num_parallel_tree" for random forest


### venv/lib/python3.13/site-packages/xgboost/spark/data.py

🟡 **L285** [技术债务]: (jiamingy): we really need a better way to bridge distributed frameworks


### venv/lib/python3.13/site-packages/google/auth/_helpers.py

🟡 **L45** [技术债务]: (https://github.com/googleapis/google-auth-library-python/issues/1684): Audit and update the list below.

🟡 **L351** [技术债务]: (https://github.com/googleapis/google-auth-library-python/issues/1701):

🟡 **L503** [技术债务]: (https://github.com/googleapis/google-auth-library-python/issues/1744):


### venv/lib/python3.13/site-packages/google/protobuf/descriptor.py

🟡 **L290** [技术债务]: Add function to calculate full_name instead of having it in

🟡 **L522** [技术债务]: We should have aggressive checking here,

🟡 **L528** [技术债务]: for this and other *Descriptor classes, we

🟡 **L576** [技术债务]: Find a way to eliminate this repetition.

🟡 **L600** [技术债务]: Find a way to eliminate this repetition.

🟡 **L637** [技术债务]: Find a way to eliminate this repetition.


### venv/lib/python3.13/site-packages/google/protobuf/text_format.py

🟡 **L22** [技术债务]: Import thread contention leads to test failures.

🟡 **L1092** [技术债务]: Change to _allow_singular_overwrites.

🟡 **L1648** [技术债务]: Migrate violators to textformat_tokenizer.


### venv/lib/python3.13/site-packages/google/protobuf/message_factory.py

🟡 **L100** [技术债务]: Remove this check here. Duplicate extension

🟡 **L140** [技术债务]: Remove this check here. Duplicate extension


### venv/lib/python3.13/site-packages/google/protobuf/message.py

🟡 **L8** [技术债务]: We should just make these methods all "pure-virtual" and move

🟡 **L182** [技术债务]: MergeFromString() should probably return None and be

🟡 **L218** [技术债务]: When we switch to a helper, this will return None.

🟡 **L263** [技术债务]: Decide whether we like these better


### venv/lib/python3.13/site-packages/google/protobuf/descriptor_pool.py

🟡 **L1364** [技术债务]: This pool could be constructed from Python code, when we


### venv/lib/python3.13/site-packages/google/auth/aio/_helpers.py

🟡 **L41** [技术债务]: (https://github.com/googleapis/google-auth-library-python/issues/1745):

🟡 **L55** [技术债务]: (https://github.com/googleapis/google-auth-library-python/issues/1755):


### venv/lib/python3.13/site-packages/google/protobuf/internal/type_checkers.py

🟡 **L35** [技术债务]: Remove this warning count after 34.0

🟡 **L160** [技术债务]: Raise errors in 2026 Q1 release

🟡 **L201** [技术债务]: Raise errors in 2026 Q1 release


### venv/lib/python3.13/site-packages/google/protobuf/internal/containers.py

🟡 **L98** [技术债务]: Remove this. BaseContainer does *not* conform to

🟡 **L214** [技术债务]: Constrain T to be a subtype of Message.


### venv/lib/python3.13/site-packages/google/protobuf/internal/api_implementation.py

🟡 **L88** [技术债务]: fail back to python


### venv/lib/python3.13/site-packages/google/protobuf/internal/builder.py

🟡 **L96** [技术债务]: Remove this on-op


### venv/lib/python3.13/site-packages/google/protobuf/internal/python_message.py

🟡 **L10** [技术债务]: Helpers for verbose, common checks like seeing if a

🟡 **L215** [技术债务]: Escape Python keywords (e.g., yield), and test this support.

🟡 **L230** [技术债务]: Remove this method entirely if/when everyone agrees with my

🟡 **L776** [技术债务]: Remove duplication with similar method

🟡 **L833** [技术债务]: Migrate all users of these attributes to functions like

🟡 **L836** [技术债务]: Use cls.MESSAGE_FACTORY.pool when available.

🟡 **L993** [技术债务]: Don't use the factory of generated messages.

🟡 **L1005** [技术债务]: For now we just strip the hostname.  Better logic will be


### venv/lib/python3.13/site-packages/google/protobuf/internal/extension_dict.py

🟡 **L37** [技术债务]: Unify error handling of "unknown extension" crap.

🟡 **L38** [技术债务]: Support iteritems()-style iteration over all


### venv/lib/python3.13/site-packages/starlette/middleware/exceptions.py

🟡 **L26** [技术债务]: We ought to handle 404 cases if debug is set.


### venv/lib/python3.13/site-packages/jedi/plugins/django.py

🟡 **L73** [技术债务]: private access..


### venv/lib/python3.13/site-packages/jedi/plugins/stdlib.py

🟡 **L189** [技术债务]: theoretically we have to check here if something is an iterator.

🟡 **L436** [技术债务]: here we only use one of the types, we should use all.

🟡 **L706** [技术债务]: we need to add the contextualized value.


### venv/lib/python3.13/site-packages/jedi/api/completion.py

🟡 **L447** [技术债务]: we should probably check here for properties


### venv/lib/python3.13/site-packages/jedi/api/__init__.py

🟡 **L111** [技术债务]: add a better warning than the traceback!

🟡 **L464** [技术债务]: here we use stubs instead of the actual values. We should use

🟡 **L501** [技术债务]: private access


### venv/lib/python3.13/site-packages/jedi/api/environment.py

🟡 **L345** [技术债务]: this function should probably return a list of environments since

🟡 **L407** [技术债务]: support Python Anaconda.


### venv/lib/python3.13/site-packages/jedi/api/classes.py

🟡 **L181** [技术债务]: move this to their respective names.


### venv/lib/python3.13/site-packages/jedi/api/helpers.py

🟡 **L131** [技术债务]: This is for now not an official parso API that exists purely


### venv/lib/python3.13/site-packages/jedi/api/project.py

🟡 **L101** [技术债务]: make django setting public?


### venv/lib/python3.13/site-packages/jedi/inference/analysis.py

🟡 **L81** [技术债务]: this path is probably not right

🟡 **L117** [技术债务]: maybe make a warning for __getattr__/__getattribute__


### venv/lib/python3.13/site-packages/jedi/inference/sys_path.py

🟡 **L52** [技术债务]: Essentially we're not checking details on sys.path


### venv/lib/python3.13/site-packages/jedi/inference/base_value.py

🟡 **L124** [技术债务]: if no __aiter__ values are there, error should be:

🟡 **L173** [技术债务]: this value is probably not right.


### venv/lib/python3.13/site-packages/jedi/inference/arguments.py

🟡 **L233** [技术债务]: this function is a bit strange. probably refactor?

🟡 **L313** [技术债务]: this funcdef should not be needed.


### venv/lib/python3.13/site-packages/jedi/inference/cache.py

🟡 **L25** [技术债务]: These checks are kind of ugly and slow.


### venv/lib/python3.13/site-packages/jedi/inference/syntax_tree.py

🟡 **L104** [技术债务]: there's a lot of issues with this one. We actually should do

🟡 **L792** [技术债务]: an exception can also be a tuple. Check for those.

🟡 **L793** [技术债务]: check for types that are not classes and add it to


### venv/lib/python3.13/site-packages/jedi/inference/filters.py

🟡 **L281** [技术债务]: add TypeError if params are given/or not correct.


### venv/lib/python3.13/site-packages/jedi/inference/gradual/typeshed.py

🟡 **L71** [技术债务]: this caches the stub files indefinitely, maybe use a time cache

🟡 **L130** [技术债务]: is this needed? where are the exceptions coming from that make this


### venv/lib/python3.13/site-packages/jedi/inference/gradual/annotation.py

🟡 **L300** [技术债务]: _dict_values is not public.


### venv/lib/python3.13/site-packages/jedi/inference/gradual/stub_value.py

🟡 **L95** [技术债务]: rewrite direct return


### venv/lib/python3.13/site-packages/jedi/inference/gradual/typing.py

🟡 **L90** [技术债务]: doesn't even exist in typeshed/typing.py, yet. But will be

🟡 **L270** [技术债务]: use inference_state.import_module?


### venv/lib/python3.13/site-packages/jedi/inference/gradual/base.py

🟡 **L124** [技术债务]: not sure if this is nice.

🟡 **L137** [技术债务]: why is this ordering the correct one?

🟡 **L139** [技术债务]: I'm still not sure gather_annotation_classes is a good

🟡 **L344** [技术债务]: this is obviously wrong. Is it though?


### venv/lib/python3.13/site-packages/jedi/inference/value/instance.py

🟡 **L377** [技术债务]: tuple initializations

🟡 **L584** [技术债务]: filter non-self assignments instead of this bad


### venv/lib/python3.13/site-packages/jedi/inference/value/iterable.py

🟡 **L267** [技术债务]: merge with _DictMixin?

🟡 **L272** [技术债务]: merge with _dict_keys?

🟡 **L372** [技术债务]: this should probably use at least part of the code


### venv/lib/python3.13/site-packages/jedi/inference/value/dynamic_arrays.py

🟡 **L37** [技术债务]: also check for dict updates


### venv/lib/python3.13/site-packages/jedi/inference/value/klass.py

🟡 **L240** [技术债务]: Do a proper mro resolution. Currently we are just listing

🟡 **L243** [技术债务]: there's multiple different mro paths possible if this yields

🟡 **L246** [技术债务]: detect for TypeError: duplicate base class str,

🟡 **L251** [技术债务]: add a TypeError like:

🟡 **L398** [技术债务]: Do a proper mro resolution. Currently we are just listing


### venv/lib/python3.13/site-packages/jedi/inference/value/function.py

🟡 **L268** [技术债务]: if is_async, wrap yield statements in Awaitable/async_generator_asend

🟡 **L436** [技术债务]: check with values if it's the right overload


### venv/lib/python3.13/site-packages/jedi/inference/compiled/access.py

🟡 **L333** [技术债务]: this API is ugly.

🟡 **L480** [技术债务]: zuban


### venv/lib/python3.13/site-packages/jedi/inference/compiled/mixed.py

🟡 **L269** [技术债务]: accessing this is bad, but it probably doesn't matter that much,

🟡 **L274** [技术债务]: Care about generics from stuff like `[1]` and don't return like this.

🟡 **L286** [技术债务]: this __name__ might be wrong.


### venv/lib/python3.13/site-packages/jedi/inference/compiled/value.py

🟡 **L217** [技术债务]: wtf is this? this is exactly the same as the thing


### venv/lib/python3.13/site-packages/databricks/sdk/useragent.py

🟡 **L233** [技术债务]: reconsider what to do if multiple providers are detected.


### venv/lib/python3.13/site-packages/databricks/sdk/credentials_provider.py

🟡 **L313** [技术债务]: We should ideally use more specific exceptions.


### venv/lib/python3.13/site-packages/databricks/sdk/data_plane.py

🟡 **L21** [技术债务]: Enable async once its stable. @oauth_credentials_provider must also have async enabled.


### venv/lib/python3.13/site-packages/databricks/sdk/oidc_token_supplier.py

🟡 **L10** [技术债务]: Check the required environment variables while creating the instance rather than in the get_oidc_token method to allow early return.


### venv/lib/python3.13/site-packages/databricks/sdk/oauth.py

🟡 **L439** [技术债务]: show better message

🟡 **L598** [技术债务]: distinguish between Databricks IDP and Azure AD


### venv/lib/python3.13/site-packages/databricks/sdk/mixins/files.py

🟡 **L167** [技术债务]: verify semantics


### venv/lib/python3.13/site-packages/databricks/sdk/mixins/open_ai_client.py

🟡 **L167** [技术债务]: Remove this once we have a better way to get back the response headers


### venv/lib/python3.13/site-packages/absl/flags/_flagvalues.py

🟡 **L331** [技术债务]: (yileiyang): Restrict default to Optional[str].

🟡 **L361** [技术债务]: (yileiyang): Restrict default to Optional[str].


### venv/lib/python3.13/site-packages/absl/testing/absltest.py

🟡 **L494** [技术债务]: (b/123775699): Once pytype supports typing.Literal, use overload and


### venv/lib/python3.13/site-packages/skops/card/_parser.py

🟡 **L85** [技术债务]: Content is a Formattable, no generic way to modify it --


### venv/lib/python3.13/site-packages/skops/card/_markup.py

🟡 **L79** [技术债务]: explain why skipping 1st item


### venv/lib/python3.13/site-packages/skops/io/_numpy.py

🟡 **L56** [技术债务]: NdArrayNode is not only responsible for np.arrays

🟡 **L99** [技术债务]: this is a hack to get the correct shape of the array. We

🟡 **L251** [技术债务]: what should we trust?


### venv/lib/python3.13/site-packages/skops/io/_visualize.py

🟡 **L296** [技术债务]: For better security, we should check the schema if we return early,

🟡 **L386** [技术债务]: it would be nice to print html representation if inside a notebook


### venv/lib/python3.13/site-packages/skops/io/_audit.py

🟡 **L244** [技术债务]: should we check the types of the keys?

🟡 **L288** [技术债务]: deal with case that __id__ is unknown or prevent it from


### venv/lib/python3.13/site-packages/skops/io/_sklearn.py

🟡 **L15** [技术债务]: remove once support for sklearn<1.2 is dropped. See #187

🟡 **L37** [技术债务]: remove once support for sklearn<1.6 is dropped.

🟡 **L268** [技术债务]: make sure trusted here makes sense and used.

🟡 **L280** [技术债务]: remove once support for sklearn<1.2 is dropped.

🟡 **L300** [技术债务]: remove once support for sklearn<1.2 is dropped.

🟡 **L355** [技术债务]: remove once support for sklearn<1.2 is dropped.


### venv/lib/python3.13/site-packages/skops/io/_general.py

🟡 **L256** [技术债务]: what do we trust?

🟡 **L300** [技术债务]: should we trust anything?

🟡 **L341** [技术债务]: what do we trust?

🟡 **L482** [技术债务]: what do we trust?

🟡 **L549** [技术债务]: what do we trust?

🟡 **L588** [技术债务]: should we consider a JsonNode always safe?


### venv/lib/python3.13/site-packages/skops/io/tests/test_persist.py

🟡 **L330** [技术债务]: make this a parameter and test with sparse data

🟡 **L331** [技术债务]: try with pandas.DataFrame as well


### venv/lib/python3.13/site-packages/skops/io/tests/test_external.py

🟡 **L77** [技术债务]: adjust once more types are trusted by default

🟡 **L179** [技术债务]: adjust once more types are trusted by default

🟡 **L331** [技术债务]: adjust once more types are trusted by default

🟡 **L408** [技术债务]: adjust once more types are trusted by default


### venv/lib/python3.13/site-packages/skops/io/tests/_utils.py

🟡 **L14** [技术债务]: Investigate why that seems to be an issue on MacOS (only observed with


### venv/lib/python3.13/site-packages/skops/io/old/_general_v0.py

🟡 **L20** [技术债务]: what do we trust?


### venv/lib/python3.13/site-packages/fontTools/cu2qu/cli.py

🟡 **L52** [技术债务]: on python3+, there's os.path.samefile


### venv/lib/python3.13/site-packages/fontTools/subset/__init__.py

🟡 **L1416** [技术债务]: We can do a second round of remapping class values based

🟡 **L2505** [技术债务]: Return emptiness...

🟡 **L2548** [技术债务]: Return emptiness...

🟡 **L2710** [技术债务]: also prune ununsed varIndices in COLR.VarStore

🟡 **L2720** [技术债务]: (anthrotype): Do The Right Thing (TM).

🟡 **L3080** [技术债务]: (behdad) Only keep one subtable?

🟡 **L3102** [技术债务]: (behdad) We drop all the default-UVS mappings

🟡 **L3148** [技术债务]: (behdad) Convert formats when needed.

🟡 **L3188** [技术债务]: (behdad) Sometimes (eg Apple Color Emoji) there's only a macroman

🟡 **L3191** [技术债务]: (behdad) Option to keep only one platform's

🟡 **L3193** [技术债务]: (behdad) This is Windows-platform specific!

🟡 **L3292** [技术债务]: (behdad) OS/2 ulCodePageRange?

🟡 **L3293** [技术债务]: (behdad) Drop AAT tables.

🟡 **L3294** [技术债务]: (behdad) Drop unneeded GSUB/GPOS Script/LangSys entries.

🟡 **L3295** [技术债务]: (behdad) Drop empty GSUB/GPOS, and GDEF if no GSUB/GPOS left

🟡 **L3296** [技术债务]: (behdad) Drop GDEF subitems if unused by lookups

🟡 **L3297** [技术债务]: (behdad) Avoid recursing too much (in GSUB/GPOS and in CFF)

🟡 **L3298** [技术债务]: (behdad) Text direction considerations.

🟡 **L3299** [技术债务]: (behdad) Text script / language considerations.

🟡 **L3300** [技术债务]: (behdad) Optionally drop 'kern' table if GPOS available

🟡 **L3302** [技术债务]: (behdad) Drop old-spec Indic scripts


### venv/lib/python3.13/site-packages/fontTools/subset/svg.py

🟡 **L63** [技术债务]: (anthrotype): Check we aren't missing other supported kinds of reference


### venv/lib/python3.13/site-packages/fontTools/voltLib/voltToFea.py

🟡 **L755** [技术债务]: Does VOLT support this?


### venv/lib/python3.13/site-packages/fontTools/merge/cmap.py

🟡 **L48** [技术债务]: Warn if advances not the same but within tolerance.

🟡 **L92** [技术债务]: Handle format=14.

🟡 **L155** [技术债务]: Try harder to do something about these.


### venv/lib/python3.13/site-packages/fontTools/merge/unicode.py

🟡 **L7** [技术债务]: Move me to unicodedata module and autogenerate.


### venv/lib/python3.13/site-packages/fontTools/merge/layout.py

🟡 **L17** [技术债务]: Do smarter merge.

🟡 **L52** [技术债务]: Support merging ReqFeatureIndex

🟡 **L117** [技术债务]: Merge duplicate entries

🟡 **L244** [技术债务]: make them do the same

🟡 **L457** [技术债务]: FeatureParams nameIDs

🟡 **L526** [技术债务]: FeatureParams nameIDs


### venv/lib/python3.13/site-packages/fontTools/merge/__init__.py

🟡 **L169** [技术债务]: Add an option to disable this?


### venv/lib/python3.13/site-packages/fontTools/merge/tables.py

🟡 **L25** [技术债务]: When we correctly merge hinting data, update these values:

🟡 **L139** [技术债务]: should really be the first Latin font

🟡 **L201** [技术债务]: ? Does mixing name records make sense?

🟡 **L238** [技术债务]: ? Appears irreconcilable


### venv/lib/python3.13/site-packages/fontTools/varLib/__init__.py

🟡 **L104** [技术债务]: Skip axes that have no variation.

🟡 **L405** [技术债务]: Modify gasp table to deactivate gridfitting for all ranges?

🟡 **L443** [技术债务]: Only drop hinting from this glyph.

🟡 **L782** [技术债务]: support gasp entries

🟡 **L962** [技术债务]: Use fontTools.designspaceLib.tagForAxisName instead.

🟡 **L1034** [技术债务]: This mapping should ideally be moved closer to logic in _add_fvar/avar

🟡 **L1242** [技术债务]: 'master_ttfs' is unused except for return value, remove later

🟡 **L1267** [技术债务]: append masters as named-instances as well; needs .designspace change.

🟡 **L1325** [技术债务]: Only return vf for 4.0+, the rest is unused.


### venv/lib/python3.13/site-packages/fontTools/varLib/mutator.py

🟡 **L413** [技术债务]: prune unused ltag tags and re-enumerate langIDs accordingly


### venv/lib/python3.13/site-packages/fontTools/varLib/varStore.py

🟡 **L589** [技术债务]: https://github.com/fonttools/fonttools/pull/3126#discussion_r1205439785

🟡 **L701** [技术债务]: allow user to configure logging via command-line options


### venv/lib/python3.13/site-packages/fontTools/varLib/interpolate_layout.py

🟡 **L57** [技术债务]: GSUB/GDEF


### venv/lib/python3.13/site-packages/fontTools/varLib/merger.py

🟡 **L295** [技术债务]: Speed up

🟡 **L351** [技术债务]: (behdad) Check and warn if that happens?

🟡 **L537** [技术债务]: When merger becomes selfless, revert e6125b353e1f54a0280ded5434b8e40d042de69f

🟡 **L557** [技术债务]: handle out-of-range?

🟡 **L627** [技术债务]: move merger to be selfless

🟡 **L697** [技术债务]: Right now we require that all marks have same class in

🟡 **L1096** [技术债务]: Handle differing valueformats


### venv/lib/python3.13/site-packages/fontTools/mtiLib/__init__.py

🟡 **L1104** [技术债务]: accept set names

🟡 **L1206** [技术债务]: BytesIO / StringIO as needed?  also, figure out whether we work on bytes or unicode


### venv/lib/python3.13/site-packages/fontTools/pens/cu2quPen.py

🟡 **L242** [技术债务]: Simplify like 3e8ebcdce592fe8a59ca4c3a294cc9724351e1ce


### venv/lib/python3.13/site-packages/fontTools/otlLib/builder.py

🟡 **L2930** [技术债务]: Instead of counting the number of glyphs in each class,


### venv/lib/python3.13/site-packages/fontTools/ufoLib/__init__.py

🟡 **L185** [技术债务]: (anthrotype): try to narrow this down a little


### venv/lib/python3.13/site-packages/fontTools/ufoLib/errors.py

🟡 **L24** [技术债务]: Replace with https://docs.python.org/3.11/library/exceptions.html#BaseException.add_note


### venv/lib/python3.13/site-packages/fontTools/designspaceLib/__init__.py

🟡 **L1912** [技术债务]: (Python 3.10): use TypeGuard

🟡 **L3291** [技术债务]: (Python 3.10): use TypeGuard


### venv/lib/python3.13/site-packages/fontTools/designspaceLib/types.py

🟡 **L123** [技术债务]: (Python 3.10): use TypeGuard


### venv/lib/python3.13/site-packages/fontTools/designspaceLib/split.py

🟡 **L93** [技术债务]: (Python 3.10): use TypeGuard

🟡 **L186** [技术债务]: (Jany) let's think about it. Not include = OK because the point of

🟡 **L204** [技术债务]: (Python 3.10): use TypeGuard

🟡 **L430** [技术债务]: Ensure that all(key in conditionset for key in region.keys())?


### venv/lib/python3.13/site-packages/fontTools/feaLib/ast.py

🟡 **L931** [技术债务]: consider lazy-loading the including parser/lexer?


### venv/lib/python3.13/site-packages/fontTools/ttLib/ttGlyphSet.py

🟡 **L51** [技术债务]: VVAR, VORG

🟡 **L182** [技术债务]: VVAR/VORG


### venv/lib/python3.13/site-packages/fontTools/ttLib/scaleUpem.py

🟡 **L168** [技术债务]: Move this code duplicated below to MultiVarStore.__getitem__,


### venv/lib/python3.13/site-packages/fontTools/ttLib/reorderGlyphs.py

🟡 **L206** [技术债务]: Port to otTraverse


### venv/lib/python3.13/site-packages/fontTools/cffLib/transforms.py

🟡 **L322** [技术债务]: CFF2 no need for endchar.


### venv/lib/python3.13/site-packages/fontTools/cffLib/CFFToCFF2.py

🟡 **L211** [技术债务]: (behdad): What does the following comment even mean? Both CFF and CFF2


### venv/lib/python3.13/site-packages/fontTools/colorLib/builder.py

🟡 **L38** [技术债务]: move type aliases to colorLib.types?

🟡 **L65** [技术债务]: apparently no builder_test confirms this works (?)

🟡 **L445** [技术债务]: feels like something itertools might have already


### venv/lib/python3.13/site-packages/fontTools/svgLib/path/shapes.py

🟡 **L23** [技术债务]: assumes a 'matrix' transform.

🟡 **L121** [技术债务]: there are more rules for adjusting rx, ry


### venv/lib/python3.13/site-packages/fontTools/varLib/instancer/__init__.py

🟡 **L446** [技术债务]: Merge this with the main codepath.

🟡 **L508** [技术债务]: (behdad) My confidence in this function is rather low;

🟡 **L1103** [技术债务]: (anthrotype) Add support for HVAR/VVAR in CFF2

🟡 **L1322** [技术债务]: (anthrotype) Support partial instancing of JSTF and BASE tables


### venv/lib/python3.13/site-packages/fontTools/varLib/instancer/names.py

🟡 **L63** [技术债务]: Only prune unused ltag tags, renumerating langIDs accordingly.

🟡 **L270** [技术债务]: (Marc F) It may be nice to make this part a standalone


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/TupleVariation.py

🟡 **L259** [技术债务]: This never switches back to a byte-encoding from a short-encoding.


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otTables.py

🟡 **L679** [技术债务]: Report this specification bug to Apple.

🟡 **L1730** [技术债务]: Handle defaults instead of defaulting to None!


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otConverters.py

🟡 **L646** [技术债务]: Cache table.hasPropagated.

🟡 **L764** [技术债务]: Clean / merge the SubTable and SubStruct

🟡 **L1924** [技术债务]: Advance reader

🟡 **L2142** [技术债务]: Automatically recompute formatFlags based on the contents of


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/E_B_D_T_.py

🟡 **L453** [技术债务]: Currently non-lazy decompilation is untested here...


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/_g_l_y_f.py

🟡 **L994** [技术债务]: (behdad): Add a configuration option for this?


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/_n_a_m_e.py

🟡 **L371** [技术债务]: Should minimize BCP 47 language codes.


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/sbixStrike.py

🟡 **L134** [技术债务]: what if there are more glyph data records than (glyf table) glyphs?


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/E_B_L_C_.py

🟡 **L375** [技术债务]: Currently non-lazy decompiling doesn't work for this class...


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/O_S_2f_2.py

🟡 **L726** [技术债务]: Symbol bit has a special meaning (check the spec), we need


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otBase.py

🟡 **L1045** [技术债务]: Handle defaults instead of defaulting to None!

🟡 **L1142** [技术债务]: Handle defaults instead of defaulting to None!


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/sbixGlyph.py

🟡 **L94** [技术债务]: if ttFont has no maxp, cmap etc., ignore glyph names and compile by index?

🟡 **L110** [技术债务]: ignore empty glyphs?


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/quart.py

🟡 **L243** [技术债务]: Figure out what to do with request body. Methods on request


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/otlp.py

🟡 **L220** [技术债务]: -neel better propagator support, chain with existing ones if possible instead of replacing


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/trytond.py

🟡 **L12** [技术债务]: trytond-worker, trytond-cron and trytond-admin intergations


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/pymongo.py

🟡 **L217** [技术债务]: remove the set_tag call in the next major release!


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/anthropic.py

🟡 **L315** [技术债务]: Record event.usage.server_tool_use


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/falcon.py

🟡 **L69** [技术债务]: (jmagnusson): Figure out if there's a way to support this


### venv/lib/python3.13/site-packages/sentry_sdk/ai/monitoring.py

🟡 **L109** [技术债务]: move pipeline name elsewhere


### venv/lib/python3.13/site-packages/sentry_sdk/profiler/__init__.py

🟡 **L28** [技术债务]: Deprecate this in favor of `start_profiler`

🟡 **L30** [技术债务]: Deprecate this in favor of `stop_profiler`


### venv/lib/python3.13/site-packages/sentry_sdk/profiler/continuous_profiler.py

🟡 **L92** [技术债务]: deprecate this and just use the existing `profiler_mode`

🟡 **L131** [技术债务]: deprecate this as it'll be replaced by the auto lifecycle option


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/redis/utils.py

🟡 **L115** [技术债务]: Remove this whole function when removing transaction based tracing


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/django/transactions.py

🟡 **L76** [技术债务]: (dcramer): it'd be nice to change these into [%s] but it currently


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/django/caching.py

🟡 **L105** [技术债务]: We don't handle `get_or_set` which we should

🟡 **L156** [技术债务]: We don't handle `get_or_set` which we should

🟡 **L193** [技术债务]: location can also be an array of locations


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/openai_agents/spans/ai_client.py

🟡 **L49** [技术债务]: -anton: remove hardcoded stuff and replace something that also works for embedding and so on


### venv/lib/python3.13/site-packages/bs4/builder/_htmlparser.py

🟡 **L160** [技术债务]: handle namespaces here?


### venv/lib/python3.13/site-packages/bs4/builder/__init__.py

🟡 **L225** [技术债务]: store_line_numbers is probably irrelevant now that

🟡 **L652** [技术债务]: This cast will fail in the (very unlikely) scenario


### venv/lib/python3.13/site-packages/bs4/builder/_html5lib.py

🟡 **L195** [技术债务]: Why is the parser 'html.parser' here? Using

🟡 **L201** [技术债务]: What are **kwargs exactly? Should they be passed in

🟡 **L258** [技术债务]: This code is not covered by the BS4 tests, and

🟡 **L349** [技术债务]: -TYPING: typeshed stubs are incorrect about this;

🟡 **L391** [技术债务]: This has O(n^2) performance, for input like

🟡 **L560** [技术债务]: -COVERAGE: This code has no test coverage and

🟡 **L581** [技术债务]: -TYPING: typeshed stubs are incorrect about this;

🟡 **L586** [技术债务]: -TYPING: typeshed stubs are incorrect about this;


### venv/lib/python3.13/site-packages/bs4/builder/_lxml.py

🟡 **L185** [技术债务]: Issue a warning if parser is present but not a

🟡 **L253** [技术债务]: This is a workaround for


### venv/lib/python3.13/site-packages/mlflow/dspy/callback.py

🟡 **L152** [技术债务]: the span may not contain model name so we cannot calculate cost


### venv/lib/python3.13/site-packages/mlflow/assistant/cli.py

🟡 **L402** [技术债务]: Update this when we support other providers


### venv/lib/python3.13/site-packages/mlflow/tracing/config.py

🟡 **L14** [技术债务]: Move more configuration options here, such as async logging, display, etc.


### venv/lib/python3.13/site-packages/mlflow/tracing/provider.py

🟡 **L798** [技术债务]: Update this logic to pluggable registry where


### venv/lib/python3.13/site-packages/mlflow/tracing/fluent.py

🟡 **L1763** [技术债务]: deprecate this function once we fully support OTel traces

🟡 **L1778** [技术债务]: remove this function in 3.7.0


### venv/lib/python3.13/site-packages/mlflow/crewai/__init__.py

🟡 **L41** [技术债务]: Handle asynchronous tasks and crew executions


### venv/lib/python3.13/site-packages/mlflow/types/type_hints.py

🟡 **L595** [技术债务]: remove the warning and raise Exception once the bug about evaluate


### venv/lib/python3.13/site-packages/mlflow/types/llm.py

🟡 **L10** [技术债务]: Switch to pydantic in a future version of MLflow.


### venv/lib/python3.13/site-packages/mlflow/types/chat.py

🟡 **L132** [技术债务]: Define a sub classes for different type of messages (request/response, and


### venv/lib/python3.13/site-packages/mlflow/types/agent.py

🟡 **L47** [技术债务]: make this a pydantic class with subtypes once we have more details on usage

🟡 **L120** [技术债务]: add finish_reason_metadata once we have a plan for usage

🟡 **L164** [技术债务]: add finish_reason_metadata once we have a plan for usage

🟡 **L209** [技术债务]: move out all params to a ParamSchema when Map(AnyType()) is supported by ParamSpec


### venv/lib/python3.13/site-packages/mlflow/types/schema.py

🟡 **L1192** [技术债务]: we will drop data conversion for params in the future, including


### venv/lib/python3.13/site-packages/mlflow/langchain/model.py

🟡 **L688** [技术债务]: We don't automatically turn tracing on in OSS model serving, because we haven't

🟡 **L693** [技术债务]: This env var was once used for controlling whether or not to inject the


### venv/lib/python3.13/site-packages/mlflow/xgboost/__init__.py

🟡 **L565** [技术债务]: Remove `replace("SNAPSHOT", "dev")` once the following issue is addressed:


### venv/lib/python3.13/site-packages/mlflow/projects/__init__.py

🟡 **L104** [技术债务]: remove this check once kubernetes execution has been refactored


### venv/lib/python3.13/site-packages/mlflow/projects/_project_spec.py

🟡 **L30** [技术债务]: Validate structure of YAML loaded from the file


### venv/lib/python3.13/site-packages/mlflow/projects/utils.py

🟡 **L249** [技术债务]: (dbczumar): Replace HTTP resolution via ``requests.get`` with an invocation of


### venv/lib/python3.13/site-packages/mlflow/projects/databricks.py

🟡 **L183** [技术债务]: Get subdirectory for experiment from the tracking server


### venv/lib/python3.13/site-packages/mlflow/llama_index/model.py

🟡 **L196** [技术债务]: make this logic cleaner and maybe a util

🟡 **L510** [技术债务]: The code path saved in the MLModel file is the local absolute path to the code


### venv/lib/python3.13/site-packages/mlflow/llama_index/tracer.py

🟡 **L363** [技术债务]: Union type hint doesn't work with singledispatchmethod, so we have to define


### venv/lib/python3.13/site-packages/mlflow/utils/mime_type_utils.py

🟡 **L8** [技术债务]: Create a module to define constants to avoid circular imports


### venv/lib/python3.13/site-packages/mlflow/utils/proto_json_utils.py

🟡 **L601** [技术债务]: Reuse this function for `inputs` key data parsing in serving, and


### venv/lib/python3.13/site-packages/mlflow/utils/rest_utils.py

🟡 **L218** [技术债务]: Update transient error handling defaults in Databricks SDK to match standard


### venv/lib/python3.13/site-packages/mlflow/utils/env_pack.py

🟡 **L115** [技术债务]: Check pip requirements using uv instead.


### venv/lib/python3.13/site-packages/mlflow/utils/providers.py

🟡 **L522** [技术债务]: uncomment this once it's supported by OpenAIConfig


### venv/lib/python3.13/site-packages/mlflow/utils/search_utils.py

🟡 **L1005** [技术债务]: Tech debt. Refactor search code into common utils, tracking server, and model


### venv/lib/python3.13/site-packages/mlflow/models/rag_signatures.py

🟡 **L73** [技术债务]: support ChainCompletionChunk in the future


### venv/lib/python3.13/site-packages/mlflow/models/python_api.py

🟡 **L107** [技术债务]: add an option to force recreating the env


### venv/lib/python3.13/site-packages/mlflow/models/model.py

🟡 **L1169** [技术债务]: Update model name


### venv/lib/python3.13/site-packages/mlflow/models/utils.py

🟡 **L84** [技术债务]: import from scoring_server after refactoring

🟡 **L1375** [技术债务]: this is still significantly slower than direct np.asarray dtype conversion

🟡 **L2060** [技术债务]: Remove this once the Databricks Unity Catalog Model Registry supports registration


### venv/lib/python3.13/site-packages/mlflow/cli/__init__.py

🟡 **L157** [技术债务]: Add tracking server argument once we have it working.


### venv/lib/python3.13/site-packages/mlflow/sklearn/__init__.py

🟡 **L514** [技术债务]: we could validate the scikit-learn version here


### venv/lib/python3.13/site-packages/mlflow/ag2/ag2_logger.py

🟡 **L91** [技术债务]: Patch generate_reply() method as well


### venv/lib/python3.13/site-packages/mlflow/transformers/__init__.py

🟡 **L760** [技术债务]: when a local checkpoint path is provided as a model, we assume it is eligible


### venv/lib/python3.13/site-packages/mlflow/agno/__init__.py

🟡 **L69** [技术债务]: Support streaming


### venv/lib/python3.13/site-packages/mlflow/tracking/client.py

🟡 **L1163** [技术债务]: Use model_id in MLflow 3.0

🟡 **L1196** [技术债务]: Use model_id in MLflow 3.0

🟡 **L3621** [技术债务]: Add parallelism support here


### venv/lib/python3.13/site-packages/mlflow/tracking/artifact_utils.py

🟡 **L62** [技术债务]: This would be much simpler if artifact_repo.download_artifacts could take the absolute path


### venv/lib/python3.13/site-packages/mlflow/tracking/fluent.py

🟡 **L3636** [技术债务]: Broaden this beyond pytorch_lightning as we add autologging support for more


### venv/lib/python3.13/site-packages/mlflow/anthropic/chat.py

🟡 **L105** [技术债务]: We should consider adding a new ContentPart type if more providers support this.


### venv/lib/python3.13/site-packages/mlflow/pytorch/__init__.py

🟡 **L600** [技术债务]: Stop persisting this information to the filesystem once we have a mechanism for


### venv/lib/python3.13/site-packages/mlflow/pytorch/_lightning_autolog.py

🟡 **L40** [技术债务]: Replace __MlflowPLCallback with Pytorch Lightning's built-in MlflowLogger


### venv/lib/python3.13/site-packages/mlflow/statsmodels/__init__.py

🟡 **L399** [技术债务]: move this to a specific mlflow.statsmodels.tsa flavor? Time series models

🟡 **L560** [技术债务]: add more autologgable methods here (e.g. fit_regularized, from_formula, etc)


### venv/lib/python3.13/site-packages/mlflow/entities/trace.py

🟡 **L85** [技术债务]: remove this once sql_warehouse_id


### venv/lib/python3.13/site-packages/mlflow/entities/run_info.py

🟡 **L66** [技术债务]: deep equality here?


### venv/lib/python3.13/site-packages/mlflow/entities/logged_model_tag.py

🟡 **L14** [技术债务]: deep equality here?


### venv/lib/python3.13/site-packages/mlflow/entities/run_tag.py

🟡 **L14** [技术债务]: deep equality here?


### venv/lib/python3.13/site-packages/mlflow/entities/trace_data.py

🟡 **L34** [技术债务]: remove this property in 3.7.0


### venv/lib/python3.13/site-packages/mlflow/entities/span.py

🟡 **L822** [技术债务]: If this grows unwieldy, consider either (a) splitting into per-provider


### venv/lib/python3.13/site-packages/mlflow/spark/__init__.py

🟡 **L280** [技术债务]: Use `Model.log` once `mlflowdbfs` supports logged model artifacts.

🟡 **L333** [技术债务]: Use `Model.log` once `mlflowdbfs` supports logged model artifacts.

🟡 **L557** [技术债务]: Remove this logic once the _HadoopFileSystem.is_filesystem_available() check

🟡 **L1099** [技术债务]: apache/spark master has made a change to do shallow copy before


### venv/lib/python3.13/site-packages/mlflow/catboost/__init__.py

🟡 **L382** [技术债务]: Support autologging


### venv/lib/python3.13/site-packages/mlflow/gateway/uc_function_utils.py

🟡 **L1** [技术债务]: Move this in mlflow/gateway/utils/uc_functions.py

🟡 **L190** [技术债务]: parametrize type

🟡 **L207** [技术债务]: check extra params in kwargs

🟡 **L229** [技术债务]: async so we can run functions in parallel

🟡 **L231** [技术债务]: make limits and wait timeout configurable


### venv/lib/python3.13/site-packages/mlflow/gateway/app.py

🟡 **L74** [技术债务]: Remove deployments server URLs after deprecation window elapses

🟡 **L312** [技术债务]: Remove deployments server URLs after deprecation window elapses

🟡 **L318** [技术债务]: Remove deployments server URLs after deprecation window elapses

🟡 **L366** [技术债务]: Remove deployments server URLs after deprecation window elapses

🟡 **L396** [技术债务]: Remove deployments server URLs after deprecation window elapses

🟡 **L402** [技术债务]: Remove deployments server URLs after deprecation window elapses


### venv/lib/python3.13/site-packages/mlflow/openai/_agent_tracer.py

🟡 **L110** [技术债务]: Trace object doesn't contain input/output. Can we get it somehow?


### venv/lib/python3.13/site-packages/mlflow/pyfunc/backend.py

🟡 **L281** [技术债务]: find approach for supporting MacOS/Windows system which does

🟡 **L296** [技术债务]: For Windows, there's no equivalent things of Unix shell's exec. Windows also


### venv/lib/python3.13/site-packages/mlflow/pyfunc/__init__.py

🟡 **L1556** [技术债务]: handle optional output columns.

🟡 **L2369** [技术债务]: support killing mlflow server launched in UDF task when spark job canceled

🟡 **L3320** [技术债务]: drop this support and raise exception in the next minor release since this

🟡 **L3340** [技术债务]: validate input example against signature


### venv/lib/python3.13/site-packages/mlflow/pyfunc/model.py

🟡 **L199** [技术债务]: ChatModel uses dataclass type hints which are not supported now, hence


### venv/lib/python3.13/site-packages/mlflow/assistant/providers/openai_compatible.py

🟡 **L432** [技术债务]: (joshuawong-db) This should be refactored into a helper function when


### venv/lib/python3.13/site-packages/mlflow/assistant/skills/agent-evaluation/scripts/validate_agent_tracing.py

🟡 **L18** [技术债务]: Update these imports with your agent's module and entry point

🟡 **L45** [技术债务]: Configure your agent's dependencies here

🟡 **L61** [技术债务]: Update this function call to match your agent's signature


### venv/lib/python3.13/site-packages/mlflow/assistant/skills/agent-evaluation/scripts/run_evaluation_template.py

🟡 **L94** [技术债务]: Configure your agent's LLM provider or other dependencies here

🟡 **L121** [技术债务]: Adjust the function call to match your agent's signature


### venv/lib/python3.13/site-packages/mlflow/metrics/genai/model_utils.py

🟡 **L43** [技术债务]: Standardize the return type of `get_endpoint` and remove this check

🟡 **L81** [技术债务]: call _load_model_or_server


### venv/lib/python3.13/site-packages/mlflow/metrics/genai/genai_metric.py

🟡 **L585** [技术债务]: Save the metric definition in a yaml file for model monitoring


### venv/lib/python3.13/site-packages/mlflow/metrics/genai/prompts/v1.py

🟡 **L7** [技术债务]: Update the default_mode and default_parameters to the correct values post experimentation


### venv/lib/python3.13/site-packages/mlflow/tracing/processor/base_mlflow.py

🟡 **L356** [技术债务]: Remove this once the new trace table UI is available that is based on V3 trace.


### venv/lib/python3.13/site-packages/mlflow/tracing/utils/__init__.py

🟡 **L1** [技术债务]: Split this file into multiple files and move under utils directory.


### venv/lib/python3.13/site-packages/mlflow/tracing/utils/prompt.py

🟡 **L8** [技术债务]: Remove tag based linking once we migrate to LinkPromptsToTraces endpoint


### venv/lib/python3.13/site-packages/mlflow/pyspark/ml/__init__.py

🟡 **L151** [技术债务]: Handle PipelineModel/CrossValidatorModel/TrainValidationSplitModel

🟡 **L786** [技术债务]: Remove this once we support non-scalar spark data types

🟡 **L1081** [技术债务]: Remove this once we support non-scalar spark data types


### venv/lib/python3.13/site-packages/mlflow/projects/backend/loader.py

🟡 **L28** [技术债务]: Should be a error when all backends are migrated here


### venv/lib/python3.13/site-packages/mlflow/server/assistant/api.py

🟡 **L402** [技术债务]: Extend this to support remote/proxy scenarios where the tracking URI may differ.


### venv/lib/python3.13/site-packages/mlflow/server/auth/__init__.py

🟡 **L4593** [技术债务]: we need to query endpoint ID by name from the database.


### venv/lib/python3.13/site-packages/mlflow/models/notebook_resources/eval_with_synthetic_example.py

🟡 **L14** [技术债务]: Spark/Pandas DataFrame with "content" and "doc_uri" columns.


### venv/lib/python3.13/site-packages/mlflow/models/evaluation/default_evaluator.py

🟡 **L274** [技术债务]: Move this to the /evaluators directory


### venv/lib/python3.13/site-packages/mlflow/models/evaluation/base.py

🟡 **L1601** [技术债务]: We should support inference_params for other model types


### venv/lib/python3.13/site-packages/mlflow/models/evaluation/utils/trace.py

🟡 **L143** [技术债务]: This check should not take precedence over the flavor-specific configuration


### venv/lib/python3.13/site-packages/mlflow/models/evaluation/evaluators/shap.py

🟡 **L67** [技术债务]: Shap explainer need to manipulate on each feature values,

🟡 **L221** [技术债务]: The explainer saver is buggy, if `get_underlying_model_flavor` return


### venv/lib/python3.13/site-packages/mlflow/models/evaluation/evaluators/classifier.py

🟡 **L40** [技术债务]: Also the model needs to be pyfunc model, not function or endpoint URI


### venv/lib/python3.13/site-packages/mlflow/system_metrics/metrics/rocm_monitor.py

🟡 **L112** [技术债务]: :


### venv/lib/python3.13/site-packages/mlflow/tracking/_model_registry/client.py

🟡 **L92** [技术债务]: Do we want to validate the name is legit here - non-empty without "/" and ":" ?


### venv/lib/python3.13/site-packages/mlflow/tracking/_model_registry/fluent.py

🟡 **L352** [技术债务]: Filter by 'source_run_id' once Databricks backend supports it


### venv/lib/python3.13/site-packages/mlflow/tracking/_tracking_service/utils.py

🟡 **L308** [技术债务]: (sueann): move to a projects utils module


### venv/lib/python3.13/site-packages/mlflow/genai/scorers/base.py

🟡 **L631** [技术债务]: Replace 'Assessment' with 'Feedback' once we migrate from the agent eval harness


### venv/lib/python3.13/site-packages/mlflow/genai/judges/adapters/gateway_adapter.py

🟡 **L515** [技术债务]: Consider extending _call_llm_provider_api to accept `tools` and return


### venv/lib/python3.13/site-packages/mlflow/entities/model_registry/model_version.py

🟡 **L36** [技术债务]: Make model_id a required field

🟡 **L218** [技术债务]: Include params, metrics, and model ID in proto

🟡 **L252** [技术债务]: Include params, metrics, and model ID in proto


### venv/lib/python3.13/site-packages/mlflow/gateway/providers/openai.py

🟡 **L398** [技术债务]: to support n > 1.


### venv/lib/python3.13/site-packages/mlflow/gateway/providers/togetherai.py

🟡 **L124** [技术债务]: this is questionable since the finish reason comes from togetherai api


### venv/lib/python3.13/site-packages/mlflow/gateway/providers/bedrock.py

🟡 **L61** [技术债务]: handle top_p, top_k, etc.

🟡 **L112** [技术债务]: handle top_p, top_k, etc.

🟡 **L264** [技术债务]: handle session token authentication

🟡 **L303** [技术债务]: work though botocore.exceptions to make this catchable.


### venv/lib/python3.13/site-packages/mlflow/store/model_registry/file_store.py

🟡 **L610** [技术债务]: Propagate tracking URI to file store directly, rather than relying on global

🟡 **L618** [技术债务]: Make this exception handling more specific

🟡 **L696** [技术债务]: Propagate tracking URI to file store directly, rather than relying on


### venv/lib/python3.13/site-packages/mlflow/store/model_registry/sqlalchemy_store.py

🟡 **L168** [技术债务]: verify schema here once we add logic to initialize the registry tables if they

🟡 **L275** [技术债务]: Replace the MlflowException with the following line once it's possible to run

🟡 **L1021** [技术债务]: Propagate tracking URI to file sqlalchemy directly, rather than relying


### venv/lib/python3.13/site-packages/mlflow/store/tracking/file_store.py

🟡 **L2626** [技术债务]: Read run ID from the metric file and pass it to the Metric constructor


### venv/lib/python3.13/site-packages/mlflow/store/tracking/sqlalchemy_store.py

🟡 **L1854** [技术债务]: Consider prior checks for null, type, param name validations, ... etc.

🟡 **L2629** [技术债务]: Consider upserting tags in a single transaction for performance

🟡 **L3372** [技术债务]: Support filtering by other entities such as params if needed


### venv/lib/python3.13/site-packages/mlflow/store/tracking/databricks_rest_store.py

🟡 **L286** [技术债务]: remove this once the endpoint is fully rolled out


### venv/lib/python3.13/site-packages/mlflow/store/artifact/databricks_sdk_artifact_repo.py

🟡 **L31** [技术债务]: The following artifact repositories should use this class. Migrate them.


### venv/lib/python3.13/site-packages/mlflow/store/artifact/models_artifact_repo.py

🟡 **L87** [技术债务]: it may be nice to fall back to the source URI explicitly here if for some reason


### venv/lib/python3.13/site-packages/mlflow/store/artifact/runs_artifact_repo.py

🟡 **L153** [技术债务]: Filter by 'source_run_id' once Databricks backend supports it


### venv/lib/python3.13/site-packages/mlflow/store/artifact/cloud_artifact_repo.py

🟡 **L136** [技术债务]: change to class method


### venv/lib/python3.13/site-packages/mlflow/pyfunc/scoring_server/__init__.py

🟡 **L488** [技术债务]: convert "invocations" to an async method to make internal logic fully non-blocking.


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/invoke_subgraph.py

🟡 **L460** [技术债务]: (@anijain2305) - Delete this function when base_hop uses invoke_subgraph infra

🟡 **L501** [技术债务]: (@anijain2305) - Delete this function when base_hop uses invoke_subgraph infra

🟡 **L1326** [技术债务]: Do we need the post compile passes in _aot_stage2b_compile_forward_or_inference?

🟡 **L1327** [技术债务]: add a real serialize function for SerializableCompiledFunction like _cache_inference_info


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/base_hop.py

🟡 **L194** [技术债务]: turn this into an error.

🟡 **L238** [技术债务]: Something special needs to happen with min cut partitioner


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/torchbind.py

🟡 **L60** [技术债务]: this is not really sufficient. While passes (hopefully) check


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/cond.py

🟡 **L348** [技术债务]: we need to materialize the bw graphs because dynamo is unable to


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/map.py

🟡 **L267** [技术债务]: we need to materialize the bw graphs because dynamo is unable to


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/local_map.py

🟡 **L485** [技术债务]: (ivankobzarev): Support exact size/stride by converting between local/global shapes.

🟡 **L543** [技术债务]: get rid of this when we can install as a subgraph

🟡 **L632** [技术债务]: get rid of this when we can install as a subgraph


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/utils.py

🟡 **L391** [技术债务]: Investigate here further which node is exactly aliasing

🟡 **L399** [技术债务]: Investigate here further which node is exactly mutating the inputs

🟡 **L671** [技术债务]: The parameter use_output_and_grad_bw is required because some operations

🟡 **L1031** [技术债务]: Return a more detailed information as to which node


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/invoke_leaf_function.py

🟡 **L774** [技术债务]: aliasing is not allowed


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/out_dtype.py

🟡 **L17** [技术债务]: to figure out a more generic approach


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/executorch_call_delegate.py

🟡 **L97** [技术债务]: support autograd


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/scan.py

🟡 **L197** [技术债务]: Support _inductor lowering

🟡 **L198** [技术债务]: Unify handling of pytrees for control flow ops, such as cond, while_loop, etc.


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/associative_scan.py

🟡 **L63** [技术债务]: find torch alternative for slice_along dim for torch.jit.script to work

🟡 **L195** [技术债务]: Support lifted arguments in inductor for associative_scan

🟡 **L196** [技术债务]: Support autograd for cases with lifted arguments for combine_mode=pointwise

🟡 **L730** [技术债务]: we need to materialize the bw graphs because dynamo is unable to

🟡 **L824** [技术债务]: torch.vmap may create composability issues

🟡 **L831** [技术债务]: Currently the gradients for the additional_inputs are not computed properly


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/auto_functionalize.py

🟡 **L150** [技术债务]: is there cases can we use slice even if stride or len(sizes) are not equal?


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/triton_kernel_wrap.py

🟡 **L1512** [技术债务]: (oulgen): Preexisting bug, if two kernel inputs are views of each

🟡 **L1560** [技术债务]: (oulgen): For performance reasons, we want to ensure that these

🟡 **L1588** [技术债务]: (oulgen): For performance reasons, we want to ensure that these


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/flex_attention.py

🟡 **L577** [技术债务]: So far only the input mutations are checked

🟡 **L908** [技术债务]: Rework DispatchKey.Autograd to py_autograd_impl


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/wrap.py

🟡 **L530** [技术债务]: (tmanlaibaatar) don't we need flat_apply here??


### venv/lib/python3.13/site-packages/torch/_prims/__init__.py

🟡 **L245** [技术债务]: This looks wrong, a number that is wrapped into a tensor

🟡 **L1013** [技术债务]: complex needs a special meta to account for its float -> complex behavior

🟡 **L1484** [技术债务]: with unbacked we should really exclude when shape[idx] == 1

🟡 **L1585** [技术债务]: this is only here to support the unsqueeze ref

🟡 **L1646** [技术债务]: consider renaming split_dim_view

🟡 **L1856** [技术债务]: review stride logic

🟡 **L2015** [技术债务]: update meta objects so this can be acquired directly

🟡 **L2094** [技术债务]: create a new return type for scalars?

🟡 **L2095** [技术债务]: currently returns integers for boolean tensors

🟡 **L2126** [技术债务]: create a new return type for scalars?

🟡 **L2127** [技术债务]: currently returns integers for boolean tensors

🟡 **L2158** [技术债务]: create a new return type for scalars?

🟡 **L2159** [技术债务]: currently returns integers for boolean tensors

🟡 **L2181** [技术债务]: move this as an option on the reference

🟡 **L2268** [技术债务]: review support arbitrary resizes

🟡 **L2428** [技术债务]: layout, pin_memory, memory_format

🟡 **L2429** [技术债务]: model requires_grad on TensorMeta

🟡 **L2476** [技术债务]: layout, pin_memory, memory_format

🟡 **L2477** [技术债务]: model requires_grad on TensorMeta

🟡 **L2519** [技术债务]: add layout, pin_memory

🟡 **L2574** [技术债务]: add layout, pin_memory

🟡 **L2618** [技术债务]: add layout

🟡 **L2705** [技术债务]: add layout and pin_memory support

🟡 **L2746** [技术债务]: The MAGMA backend returns V, so this is wrong if used with the MAGMA backend

🟡 **L2874** [技术债务]: we should more seriously review randomness modeling and prims


### venv/lib/python3.13/site-packages/torch/_prims/context.py

🟡 **L61** [技术债务]: Should these methods be mapped some other way?


### venv/lib/python3.13/site-packages/torch/_prims/rng_prims.py

🟡 **L264** [技术债务]: you don't need to do this, the dispatch here already disabled


### venv/lib/python3.13/site-packages/torch/_prims/executor.py

🟡 **L61** [技术债务]: caching


### venv/lib/python3.13/site-packages/torch/_logging/_internal.py

🟡 **L43** [技术债务]: Maybe we should allow for some sub-hierarchy so you can control which

🟡 **L1414** [技术债务]: deal with structured logging that occurs outside of specific compile ids

🟡 **L1499** [技术债务]: Actually, the rank probably should just be emitted once at


### venv/lib/python3.13/site-packages/torch/_functorch/partitioners.py

🟡 **L2431** [技术债务]: (chilli): This is the most questionable of the 3 heuristics for banning recompute.

🟡 **L2509** [技术债务]: I'm not totally sure why this heuristic matters. It's possible that this is

🟡 **L3093** [技术债务]: (chilli): Normalize this to also return ms

🟡 **L3362** [技术债务]: (chilli): Estimated doesn't align exactly with actual - actual is

🟡 **L3523** [技术债务]: maybe use a different process group?


### venv/lib/python3.13/site-packages/torch/_functorch/config.py

🟡 **L371** [技术债务]: turn on by default

🟡 **L376** [技术债务]: once AOT compile calls aot autograd directly instead of

🟡 **L412** [技术债务]: (ivankobzarev): Remove this config, being able to deduce it compile time.

🟡 **L419** [技术债务]: (ivankobzarev): Remove this config once extra memory usage is investigated.


### venv/lib/python3.13/site-packages/torch/_functorch/autograd_function.py

🟡 **L216** [技术债务]: update following link from master to stable once that's out

🟡 **L331** [技术债务]: Update link to stable once that's out

🟡 **L346** [技术债务]: Update link to stable once that's out

🟡 **L928** [技术债务]: - there is missing functionality here, where


### venv/lib/python3.13/site-packages/torch/_functorch/pytree_hacks.py

🟡 **L9** [技术债务]: remove this file when the migration of the pytree utility is done


### venv/lib/python3.13/site-packages/torch/_functorch/pyfunctorch.py

🟡 **L129** [技术债务]: would be nice to assert that the layers are the same, but


### venv/lib/python3.13/site-packages/torch/_functorch/aot_autograd.py

🟡 **L507** [技术债务]: Chillee argues that dynamo itself should pass in fake tensors to

🟡 **L803** [技术债务]: We actually could use the pytree path to make better descs.

🟡 **L952** [技术债务]: There's something a bit suspicious here; typically simplified

🟡 **L974** [技术债务]: These tracing_context fields should become unnecessary once we

🟡 **L985** [技术债务]: Might be nice to hold on to the Dynamo source here in full_args_descs!

🟡 **L1104** [技术债务]: it would be better to put pytree information in here

🟡 **L1140** [技术债务]: This doesn't seem to be used in any nontrivial way, check if it's

🟡 **L1264** [技术债务]: There is something deeply wrong here; compiled_fn running with

🟡 **L1414** [技术债务]: Maybe this should be in create_aot_state?  Not sure, that would

🟡 **L1468** [技术债务]: Consider if we should allow_in_graph the result by default.

🟡 **L1531** [技术债务]: do I need to filter? I hope not!

🟡 **L1686** [技术债务]: subsume this path with the aot_stage2_graph_capture path

🟡 **L1839** [技术债务]: we might have to temporarily patch config.functionalize_rng


### venv/lib/python3.13/site-packages/torch/_functorch/compilers.py

🟡 **L199** [技术债务]: There is some sort of problem where we record that an


### venv/lib/python3.13/site-packages/torch/_functorch/eager_transforms.py

🟡 **L107** [技术债务]: Remove the following hack for namedtuples

🟡 **L140** [技术债务]: this is more accurate - enable in 3.11


### venv/lib/python3.13/site-packages/torch/_functorch/vmap.py

🟡 **L164** [技术债务]: See if we can explain how flat works to the type checker


### venv/lib/python3.13/site-packages/torch/_functorch/make_functional.py

🟡 **L302** [技术债务]: We don't need to copy the model to create a stateless copy

🟡 **L357** [技术债务]: We don't need to copy the model to create a stateless copy


### venv/lib/python3.13/site-packages/torch/_numpy/_reductions_impl.py

🟡 **L412** [技术债务]: (Mario) Doesn't np.quantile accept a tuple?


### venv/lib/python3.13/site-packages/torch/_numpy/_unary_ufuncs_impl.py

🟡 **L70** [技术债务]: set __name__ and __qualname__


### venv/lib/python3.13/site-packages/torch/_numpy/random.py

🟡 **L162** [技术债务]: check a.dtype is integer -- cf np.random.choice(3.4) which raises


### venv/lib/python3.13/site-packages/torch/_numpy/_ndarray.py

🟡 **L669** [技术债务]: and they have the same dtype, device, etc


### venv/lib/python3.13/site-packages/torch/_numpy/_util.py

🟡 **L237** [技术债务]: handle _CopyMode.IF_NEEDED correctly


### venv/lib/python3.13/site-packages/torch/_export/converter.py

🟡 **L816** [技术债务]: convert sourceRange() into stack_trace

🟡 **L889** [技术债务]: convert sourceRange() into stack_trace

🟡 **L948** [技术债务]: convert sourceRange() into stack_trace

🟡 **L1029** [技术债务]: (1/N) stage.

🟡 **L1194** [技术债务]: support aten::enable_grad in both TorchScript and Converter.

🟡 **L1271** [技术债务]: Revisit this later after HigherOrderOp design changes.

🟡 **L1529** [技术债务]: adjust input orders to match GraphSignature convention


### venv/lib/python3.13/site-packages/torch/_export/pass_base.py

🟡 **L121** [技术债务]: (tmanlaibaatar) properly support Quantized FakeTensor

🟡 **L127** [技术债务]: we should allocate static shapes

🟡 **L136** [技术债务]: This is just a workaround to get over the

🟡 **L166** [技术债务]: (tmanlaibaatar) properly support Quantized FakeTensor

🟡 **L175** [技术债务]: This is just a workaround to get over the

🟡 **L329** [技术债务]: (angelayi): Update this with what we decide to do for metadata in


### venv/lib/python3.13/site-packages/torch/_export/utils.py

🟡 **L101** [技术债务]: some annoying circular dependency issue

🟡 **L920** [技术债务]: Directly provide inspect.signature compatible TS-d module.

🟡 **L925** [技术债务]: (jiashenc): TorchScript should only allow positional or keywords arguments.


### venv/lib/python3.13/site-packages/torch/_export/non_strict_utils.py

🟡 **L412** [技术债务]: (avik): refactor Dynamo to avoid duplication of the following code

🟡 **L599** [技术债务]: (avik): Maybe record the constraint violation error instead and replay later?


### venv/lib/python3.13/site-packages/torch/_export/verifier.py

🟡 **L37** [技术债务]: (angelayi): remove this in favor of _check_val

🟡 **L55** [技术债务]: (zhxchen17) Remove Tensor.

🟡 **L225** [技术债务]: Remove this allowlist.

🟡 **L237** [技术债务]: (tmanlaibaatar)

🟡 **L271** [技术债务]: (tmanlaibaatar) more proper way is needed here

🟡 **L284** [技术债务]: (T140410192): should have fake tensor for all dialects

🟡 **L347** [技术债务]: (zhxchen17)


### venv/lib/python3.13/site-packages/torch/_dispatch/python.py

🟡 **L93** [技术债务]: test the specs match; empirically  sometimes we have a tuple

🟡 **L148** [技术债务]: suppress guards

🟡 **L158** [技术债务]: This probably does the wrong thing if you're running other


### venv/lib/python3.13/site-packages/torch/_subclasses/functional_tensor.py

🟡 **L199** [技术债务]: right now, _make_wrapper_subclass's dynamic shape interaction is not great.

🟡 **L728** [技术债务]: the flatten here can potentially be deduped with the

🟡 **L754** [技术债务]: pull these from aot autograd


### venv/lib/python3.13/site-packages/torch/_subclasses/meta_utils.py

🟡 **L150** [技术债务]: move "assert_eq(m1.layout, m2.layout)" out of sparse

🟡 **L172** [技术债务]: test if is resizable (no direct query for this atm)

🟡 **L173** [技术债务]: audit AutogradMeta to see if it matches

🟡 **L174** [技术债务]: test forward AD

🟡 **L309** [技术债务]: TBH, functorch wrapped tensors probably should have

🟡 **L357** [技术债务]: It's pretty suspicious that functional tensors don't have

🟡 **L402** [技术债务]: Is it important to enable torch.inference_mode before querying

🟡 **L450** [技术债务]: I actually think recursing here is correct, but we have at

🟡 **L943** [技术债务]: how to check _TensorT?

🟡 **L1050** [技术债务]: make a dedicated UnknownSource for this?

🟡 **L1372** [技术债务]: Change this logic to use view replay for consistency?

🟡 **L1640** [技术债务]: Handle this better in Dynamo?

🟡 **L1659** [技术债务]: This doesn't seem right, where's the MKLDNN'ness

🟡 **L1709** [技术债务]: why aren't the recursive calls going to

🟡 **L1781** [技术债务]: Actually this all probably doesn't

🟡 **L1789** [技术债务]: is_leaf/requires_grad?

🟡 **L2228** [技术债务]: zero tensors?  We appear to have eliminated them by

🟡 **L2232** [技术债务]: This can probably be simplified quite a bit

🟡 **L2312** [技术债务]: return the description for later


### venv/lib/python3.13/site-packages/torch/_subclasses/fake_impls.py

🟡 **L157** [技术债务]: no real reason to restrict multiple outputs

🟡 **L223** [技术债务]: file issue

🟡 **L302** [技术债务]: I think this does the wrong thing if r is inp

🟡 **L338** [技术债务]: refactor to lambda so we don't instantiate extra errors before

🟡 **L1213** [技术债务]: consider a memo

🟡 **L1545** [技术债务]: ref

🟡 **L1793** [技术债务]: We can make this a little more faithful with best effort

🟡 **L1998** [技术债务]: Minor optimization: track if the shapes

🟡 **L2044** [技术债务]: we don't need the compute type

🟡 **L2067** [技术债务]: is_non-overlapping_and_dense not bound from Python


### venv/lib/python3.13/site-packages/torch/_subclasses/fake_tensor.py

🟡 **L67** [技术债务]: Hack to unblock https://github.com/pytorch/pytorch/pull/108186

🟡 **L509** [技术债务]: callback might be used in recursive contexts, in

🟡 **L781** [技术债务]: Generalize this as needed, e.g., into a trie of memos, if

🟡 **L1463** [技术债务]: This is a temporary measure, see

🟡 **L2000** [技术债务]: support caching sparse outputs?

🟡 **L2930** [技术债务]: Is this really needed?

🟡 **L2957** [技术债务]: Remove these exclusions, so that we can remove

🟡 **L2978** [技术债务]: - we should be use the prim aten impl

🟡 **L3450** [技术债务]: also check metadata change on inputs


### venv/lib/python3.13/site-packages/torch/_subclasses/schema_check_mode.py

🟡 **L104** [技术债务]: This is only OK if can't have NaN quantized; idk if


### venv/lib/python3.13/site-packages/torch/_subclasses/fake_utils.py

🟡 **L269** [技术债务]: enable_python_dispatcher() here


### venv/lib/python3.13/site-packages/torch/nn/_reduction.py

🟡 **L22** [技术债务]: remove once JIT exceptions support control flow


### venv/lib/python3.13/site-packages/torch/nn/functional.py

🟡 **L1606** [技术债务]: Properly support no-batch-dim inputs. For now, these are NOT supported; passing

🟡 **L2765** [技术债务]: Remove this once script supports type() calls

🟡 **L2845** [技术债务]: make use of reduce like below when JIT is ready with the missing features:

🟡 **L6952** [技术债务]: finish disentangling control flow so we don't do in-projections when statics are passed

🟡 **L6966** [技术债务]: finish disentangling control flow so we don't do in-projections when statics are passed


### venv/lib/python3.13/site-packages/torch/onnx/__init__.py

🟡 **L60** [技术债务]: (justinchuby): Remove these two properties


### venv/lib/python3.13/site-packages/torch/distributed/_state_dict_utils.py

🟡 **L109** [技术债务]: should we use pytree?

🟡 **L624** [技术债务]: currently, we cannot handle strided sharding if the dp dimension is not even. For example,

🟡 **L732** [技术债务]: We should consolidate the code here as some not all modules can depend on


### venv/lib/python3.13/site-packages/torch/distributed/distributed_c10d.py

🟡 **L269** [技术债务]: refactor into enum/strenum

🟡 **L840** [技术债务]: moco benchmark on CPU initializes pgnccl backend today, triggered this assert in CI before it was

🟡 **L1166** [技术债务]: remove this once the ecosystem moves away from it.

🟡 **L1207** [技术债务]: (yifu): remove this function once ranks + tag is not a supported

🟡 **L2113** [技术债务]: figure out pg option conversion for torchComms.

🟡 **L2164** [技术债务]: remove this check after lazy initialization is supported

🟡 **L2276** [技术债务]: This defaults to the old behavior for PythonProcessGroups which overwrites the

🟡 **L2976** [技术债务]: We need to also support torch inductor for the time estimator.

🟡 **L5424** [技术债务]: (whc) apparently some existing test case for monitored_barrier passes in a timeout in float format?

🟡 **L5494** [技术债务]: why is group count incremented only in the else path?

🟡 **L5655** [技术债务]: figure out pg option for torchComms

🟡 **L6198** [技术债务]: Use itertools.batched(get_process_group_ranks(group=group), group_size) instead when Python 3.12 is supported.

🟡 **L6343** [技术债务]: copy settings and timeout from default PG


### venv/lib/python3.13/site-packages/torch/distributed/_functional_collectives.py

🟡 **L1639** [技术债务]: (yifu): remove these in functional collective beta release

🟡 **L1679** [技术债务]: add a type,

🟡 **L1699** [技术债务]: type is actually c10d ReduceOp. is this ok?

🟡 **L1700** [技术债务]: add a type


### venv/lib/python3.13/site-packages/torch/distributed/device_mesh.py

🟡 **L104** [技术债务]: to remove it once we move all use cases into new API.

🟡 **L129** [技术债务]: to remove it once we move all use cases into new API.

🟡 **L770** [技术债务]: compiler + device_mesh slicing.

🟡 **L1006** [技术债务]: Remove the below check and define the expected behavior.

🟡 **L1017** [技术债务]: Eventually we will just directly throw error here because

🟡 **L1026** [技术债务]: to make this use case by other components public API in the future.

🟡 **L1347** [技术债务]: To make backend init more efficient with cute layout representation and support


### venv/lib/python3.13/site-packages/torch/autograd/graph.py

🟡 **L730** [技术债务]: This is almost definitely a bug.

🟡 **L745** [技术债务]: This is almost definitely a bug.


### venv/lib/python3.13/site-packages/torch/autograd/forward_ad.py

🟡 **L106** [技术债务]: We specify that __debug__ must be True because


### venv/lib/python3.13/site-packages/torch/autograd/__init__.py

🟡 **L132** [技术债务]: We can remove this conditional once we uniformly use


### venv/lib/python3.13/site-packages/torch/autograd/profiler_legacy.py

🟡 **L31** [技术债务]: change to `FutureWarning`


### venv/lib/python3.13/site-packages/torch/autograd/gradcheck.py

🟡 **L710** [技术债务]: handle the other Ju

🟡 **L955** [技术债务]: To cover more problematic cases, replace stride = 0 check with

🟡 **L1953** [技术债务]: replicate https://github.com/pytorch/pytorch/pull/77743 for fast gradcheck as well

🟡 **L2252** [技术债务]: do we want to test this too?


### venv/lib/python3.13/site-packages/torch/autograd/profiler.py

🟡 **L246** [技术债务]: Consider changing _function_events into data structure with size cap

🟡 **L909** [技术债务]: TorchScript ignores standard type annotation here

🟡 **L947** [技术债务]: Too slow with __torch_function__ handling enabled

🟡 **L985** [技术债务]: Too slow with __torch_function__ handling enabled

🟡 **L1251** [技术债务]: find in sqlite database


### venv/lib/python3.13/site-packages/torch/fx/operator_schemas.py

🟡 **L107** [技术债务]: Figure out if this is safe. It seems like when generating the type signatures for

🟡 **L282** [技术债务]: (chilli): Figure out the right way for mypy to handle this


### venv/lib/python3.13/site-packages/torch/fx/traceback.py

🟡 **L77** [技术债务]: add logging to tlparse


### venv/lib/python3.13/site-packages/torch/fx/graph.py

🟡 **L296** [技术债务]: These should return Iterator[Node], but doing so causes ~350

🟡 **L1296** [技术债务]: should return list[Node], see _node_list.__iter__ comment

🟡 **L1412** [技术债务]: should return list[Node], see _node_list.__iter__ comment

🟡 **L1545** [技术债务]: Generalize this invariant to all FX node args once the broader

🟡 **L2076** [技术债务]: consider caching `expr_to_proxy` / `sym_size_sources` across

🟡 **L2337** [技术债务]: should return Node, see _node_list.__iter__ comment


### venv/lib/python3.13/site-packages/torch/fx/_symbolic_trace.py

🟡 **L464** [技术债务]: binary search

🟡 **L731** [技术债务]: type annotations for *args and **kwargs

🟡 **L747** [技术债务]: annotate return type. inspect.get_annotations(flatten_fn)


### venv/lib/python3.13/site-packages/torch/fx/node.py

🟡 **L89** [技术债务]: Either refactor this into 2 functions 1 dce for functional graphs and 1 dce for all graphs,

🟡 **L295** [技术债务]: narrow this to TensorType | _DynType | None


### venv/lib/python3.13/site-packages/torch/fx/_graph_pickler.py

🟡 **L44** [技术债务]: This list is pretty pessimistic right now. What's the full list?

🟡 **L547** [技术债务]: make common w/ _output_from_cache_entry() in fake_tensor.py?

🟡 **L745** [技术债务]: raise a BypassFxGraphCache so we will just bypass this one...

🟡 **L918** [技术债务]: Do we really need all of this?


### venv/lib/python3.13/site-packages/torch/_prims_common/__init__.py

🟡 **L54** [技术债务]: Type[torch.SymInt], Type[torch.SymFloat]

🟡 **L56** [技术债务]: This needs a lot more type annotations

🟡 **L141** [技术债务]: look at using torch.testing.assert_close instead with an option

🟡 **L232** [技术债务]: Check the symbols are consistent with each other

🟡 **L581** [技术债务]: are these necessary?

🟡 **L1238** [技术债务]: type error here is real, replace with sym_complex

🟡 **L1258** [技术债务]: sym_complex_float?

🟡 **L1406** [技术债务]: maybe unify with can_cast_to?

🟡 **L1562** [技术债务]: when NumberType contains the sym types, can simplify this

🟡 **L1856** [技术债务]: maybe inform the user of channels_last_3d if rank of the tensor is 5?

🟡 **L2175** [技术债务]: a better way to handle this would be with a new op, "_unsafe_as_strided"


### venv/lib/python3.13/site-packages/torch/_prims_common/wrappers.py

🟡 **L186** [技术债务]: handle tuples of tensors

🟡 **L463** [技术债务]: There is a subtle bug here: prims like copy_to

🟡 **L480** [技术债务]: when tracing this will add torch tensors and not TensorMeta objects

🟡 **L482** [技术债务]: this wrapper is currently untested


### venv/lib/python3.13/site-packages/torch/multiprocessing/spawn.py

🟡 **L241** [技术债务]: investigate why spawn does not work with threadpool and raises SIGINT


### venv/lib/python3.13/site-packages/torch/multiprocessing/reductions.py

🟡 **L323** [技术债务]: Handle distinguishing between subclass and non-subclass versions of NT better

🟡 **L637** [技术债务]: Maybe this should be in tensor_classes? :)


### venv/lib/python3.13/site-packages/torch/cuda/__init__.py

🟡 **L462** [技术债务]: (torch_deploy): this accesses linecache, which attempts to read the


### venv/lib/python3.13/site-packages/torch/_decomp/decompositions_for_jvp.py

🟡 **L30** [技术债务]: The mechanism we are using to register decompositions doesn't

🟡 **L100** [技术债务]: do these also belong here?


### venv/lib/python3.13/site-packages/torch/_decomp/decompositions.py

🟡 **L78** [技术债务]: pretty sure this is not quite right

🟡 **L390** [技术债务]: None of these loss castings are quite correct, see

🟡 **L1628** [技术债务]: this doesn't appear to have enough precision in bfloat16

🟡 **L1832** [技术债务]: Take a closer look at the type promotion semantics

🟡 **L2180** [技术债务]: this decomposition is NOT here to stay. We would much prefer replacing native_batch_norm

🟡 **L2851** [技术债务]: make minimum accept scalars

🟡 **L5265** [技术债务]: handling of slice


### venv/lib/python3.13/site-packages/torch/_decomp/__init__.py

🟡 **L36** [技术债务]: relax key type here; torch registrations should be possible to; but


### venv/lib/python3.13/site-packages/torch/_decomp/decompositions_for_rng.py

🟡 **L30** [技术债务]: - We have to register many more distributions here, and also higher level

🟡 **L176** [技术债务]: Investigate if there is a better way to wrap the tuple in a


### venv/lib/python3.13/site-packages/torch/xpu/__init__.py

🟡 **L937** [技术债务]: pyzes lacks zesFrequencyGetProperties, so we cannot filter by

🟡 **L1003** [技术债务]: pyzes lacks zesPowerGetProperties, so we cannot filter by

🟡 **L1085** [技术债务]: zesDeviceEnumEngineGroups does not return ZE_RESULT_ERROR_INSUFFICIENT_PERMISSIONS on privilege errors;

🟡 **L1311** [技术债务]: Some drivers report physicalSize as 0 on client GPUs; fall back to


### venv/lib/python3.13/site-packages/torch/masked/_ops.py

🟡 **L547** [技术债务]: eliminate this restriction

🟡 **L1421** [技术债务]: compute count analytically

🟡 **L1642** [技术债务]: compute count analytically

🟡 **L1656** [技术债务]: replace torch.subtract/divide/square/maximum with

🟡 **L1828** [技术债务]: eliminate mask_input as unnecessary when using masked divide.

🟡 **L1832** [技术债务]: replace torch.maximum with masked maximum when available.

🟡 **L1834** [技术债务]: replace torch.divide with masked divide when available.


### venv/lib/python3.13/site-packages/torch/optim/radam.py

🟡 **L500** [技术债务]: (mlazos): we should try and get a foreach_where op https://github.com/pytorch/pytorch/issues/117884


### venv/lib/python3.13/site-packages/torch/optim/adam.py

🟡 **L108** [技术债务]: (crcrpar): [low prec params & their higher prec copy]


### venv/lib/python3.13/site-packages/torch/optim/_functional.py

🟡 **L21** [技术债务]: use foreach API in optim._functional to do all the computation


### venv/lib/python3.13/site-packages/torch/_inductor/dtype_propagation.py

🟡 **L230** [技术债务]: - we avoid calling this in codegen, needs work for non codegen use cases

🟡 **L396** [技术债务]: - need to handle multiple outputs

🟡 **L452** [技术债务]: - way of registering dtype for op in backend


### venv/lib/python3.13/site-packages/torch/_inductor/cudagraph_trees.py

🟡 **L217** [技术债务]: - remove, prevents cleanup

🟡 **L284** [技术债务]: - when issue #91395 is landed, we can set a weakref on

🟡 **L1075** [技术债务]: register_generator_state should potentially take explicit device

🟡 **L1749** [技术债务]: - should we make the storage resizable ?

🟡 **L2049** [技术债务]: make generation increment configurable, warn on overwrite.

🟡 **L2684** [技术债务]: we could also allow the these weak refs to continue to be allocated,


### venv/lib/python3.13/site-packages/torch/_inductor/select_algorithm.py

🟡 **L1264** [技术债务]: we should have intermediary var shapes

🟡 **L1906** [技术债务]: Maybe unify CUTLASSTemplateKernel to also use PartialRender for flexible epilogue fusion.

🟡 **L3279** [技术债务]: (AlnisM): Does tile_shape always exist?

🟡 **L3882** [技术债务]: (jgong5): support multi-template on CPU C++ backend

🟡 **L3888** [技术债务]: - assert that we have not mutating kernels here

🟡 **L4145** [技术债务]: (nmacchioni): remove this layer of abstraction

🟡 **L5949** [技术债务]: (coconutruben): replace this with taking KernelInputs as the


### venv/lib/python3.13/site-packages/torch/_inductor/ops_handler.py

🟡 **L258** [技术债务]: Better explain how the "collective" semantics of these ops;

🟡 **L280** [技术债务]: in practice, this seems to actually return None, but not returning


### venv/lib/python3.13/site-packages/torch/_inductor/codecache.py

🟡 **L756** [技术债务]: These tensors don't currently pickle, so we can't cache a compiled

🟡 **L1520** [技术债务]: change to more holistic config rather than bundled_autograd_cache

🟡 **L1877** [技术债务]: (masnesral): Investigate whether it's beneficial to store compiled graphs

🟡 **L2533** [技术债务]: (benjaminglass1): the CMake packaging path doesn't support linking files

🟡 **L3384** [技术债务]: unify to always use mmap_weights

🟡 **L5072** [技术债务]: Make the typing hint strong here


### venv/lib/python3.13/site-packages/torch/_inductor/optimize_indexing.py

🟡 **L61** [技术债务]: - there are dominated uses whose dtype does not depend on whether

🟡 **L82** [技术债务]: - not sure if we should be doing int/float casts while tracing,

🟡 **L120** [技术债务]: - if dominated node of one to_dtype is not expressible in int32,


### venv/lib/python3.13/site-packages/torch/_inductor/cpp_builder.py

🟡 **L1259** [技术债务]: (T203137008) Can we unify these flags with triton_cc_command?

🟡 **L2766** [技术债务]: make this work beyond CUDA


### venv/lib/python3.13/site-packages/torch/_inductor/cpu_vec_isa.py

🟡 **L88** [技术债务]: extend the no-import path to Windows once its CI build is green

🟡 **L299** [技术债务]: use cflags

🟡 **L471** [技术债务]: use cflags

🟡 **L572** [技术债务]: add sve256 support


### venv/lib/python3.13/site-packages/torch/_inductor/config.py

🟡 **L603** [技术债务]: @bobrenjc93 to roll this out to a few internal models to ensure this works

🟡 **L873** [技术债务]: (xuanzh): harden this to make it non optional

🟡 **L1213** [技术债务]: - need estimated and profile based version

🟡 **L1279** [技术债务]: (ivankobzarev): change default to "error" after real-world testing.

🟡 **L1372** [技术债务]: Set directly after internal rollout.

🟡 **L1553** [技术债务]: remove later

🟡 **L1833** [技术债务]: - need to debug why this prevents cleanup

🟡 **L1893** [技术债务]: - enable by default

🟡 **L2237** [技术债务]: Move this into metadata

🟡 **L2241** [技术债务]: Move this into metadata

🟡 **L2263** [技术债务]: Move this somewhere else, since it's no longer really a config


### venv/lib/python3.13/site-packages/torch/_inductor/compile_fx_ext.py

🟡 **L383** [技术债务]: For memory purposes should we log to a file and then respond with that?

🟡 **L454** [技术债务]: Do we need to figure out what changed in TracingContext in the

🟡 **L527** [技术债务]: scuba record about not being able to do this?

🟡 **L560** [技术债务]: Should we split the input into multiple sections where each

🟡 **L676** [技术债务]: make this a FxCompileMode value?


### venv/lib/python3.13/site-packages/torch/_inductor/comms.py

🟡 **L314** [技术债务]: (ivankobzarev): Remove after confirmation that runtime estimations are correct.

🟡 **L1432** [技术债务]: (ivankobzarev): Remove them after confirming,

🟡 **L2160** [技术债务]: node_summary was written without FusedSchedulerNode in mind, generally needs to be hardened

🟡 **L2172** [技术债务]: - this function probably doesn't do a very good job estimating the runtime because it doesn't carefully model


### venv/lib/python3.13/site-packages/torch/_inductor/memory.py

🟡 **L1041** [技术债务]: remove after ensuring OSS side is safe

🟡 **L1070** [技术债务]: remove after ensuring OSS side is safe


### venv/lib/python3.13/site-packages/torch/_inductor/async_compile.py

🟡 **L882** [技术债务]: This starts the SubprocPool's internal process pool as early as possible at


### venv/lib/python3.13/site-packages/torch/_inductor/distributed_autotune.py

🟡 **L238** [技术债务]: Do we really need to externally compute this value? If it's

🟡 **L263** [技术债务]: It seems like it would be better if the template could provide


### venv/lib/python3.13/site-packages/torch/_inductor/pattern_matcher.py

🟡 **L1815** [技术债务]: Revisit the functionalize_rng_ops for lowmem dropout

🟡 **L2583** [技术债务]: - look into using aot autograd, asserting no mutating ops here

🟡 **L2748** [技术债务]: remove in follow up diff, used internally


### venv/lib/python3.13/site-packages/torch/_inductor/graph.py

🟡 **L613** [技术债务]: this should not be needed once #93059 lands

🟡 **L615** [技术债务]: make a dedicated UnknownSource for this?

🟡 **L842** [技术债务]: - get different values per hardware

🟡 **L1303** [技术债务]: (chilli): We can remove the last check once we turn buffers into

🟡 **L1328** [技术债务]: (jansel): handle input aliasing

🟡 **L2120** [技术债务]: (jansel): introduce a store vs inline choice

🟡 **L2331** [技术债务]: (Eikan): Only support mixing cpu and other device now.

🟡 **L2566** [技术债务]: need to consolidate the logic between AOT and JIT

🟡 **L2688** [技术债务]: . Revisit this once the logging API is more mature


### venv/lib/python3.13/site-packages/torch/_inductor/lowering.py

🟡 **L138** [技术债务]: (rec): torch._higher_order_ops._foreach_map is not an OpOverload

🟡 **L256** [技术债务]: (jansel): ezyang says we won't need this in the future, try removing it

🟡 **L272** [技术债务]: (jansel): add quantized types?

🟡 **L392** [技术债务]: this is a crude approximation for promoting args

🟡 **L503** [技术债务]: maybe we need to use pytrees here

🟡 **L1353** [技术债务]: It would be better to realize the input if any of its sizes

🟡 **L1424** [技术债务]: Laith is there better check

🟡 **L2131** [技术债务]: origins is a set of FX nodes attached to IR nodes during

🟡 **L2166** [技术债务]: <leslie> Remove this fallback when we support vectorization

🟡 **L2252** [技术债务]: We observed negative performance impact of pointwise_cat optimization on CPU so disabled it.

🟡 **L2605** [技术债务]: don't guard on static shape here

🟡 **L2661** [技术债务]: delete once triton adds native support

🟡 **L2898** [技术债务]: mlazos reevaluate if we want to codegen something different

🟡 **L3274** [技术债务]: combine this with require_contiguous after

🟡 **L4436** [技术债务]: Calling to_device(x, device) should work but

🟡 **L4807** [技术债务]: use a masked store for this. currently only triton

🟡 **L4965** [技术债务]: Need to support more reduction type

🟡 **L5609** [技术债务]: Generalize to other max pooling flavors

🟡 **L6038** [技术债务]: should we force these to be realized?

🟡 **L6427** [技术债务]: remove this when #100331 is merged. We only do this

🟡 **L8600** [技术债务]: when graph_partition is enabled, skip - partitioning handles control flow

🟡 **L8614** [技术债务]: when graph_partition is enabled, skip - partitioning handles control flow

🟡 **L8816** [技术债务]: getattr


### venv/lib/python3.13/site-packages/torch/_inductor/compile_fx.py

🟡 **L226** [技术债务]: make this configurable

🟡 **L952** [技术债务]: This is a hack purely to get some info to extract_tensor_metadata_for_cache_key,

🟡 **L967** [技术债务]: this time will be slightly inconsistent with the one computed

🟡 **L1131** [技术债务]: add remote cache get/put timings here too

🟡 **L1232** [技术债务]: We should probably eventually add some kind of async version of this

🟡 **L1263** [技术债务]: _CompileFxKwargs actually has stronger types than in the

🟡 **L1325** [技术债务]: Should we actually dump this?  It should be redundant with the aot

🟡 **L1437** [技术债务]: (T216453900): need to work around for now to support vllm

🟡 **L1544** [技术债务]: The switching between AOT mode and not here is a bit

🟡 **L1730** [技术债务]: Hoist this above V.aot_compilation

🟡 **L2024** [技术债务]: - could make one single op of multiple slices

🟡 **L2128** [技术债务]: Take compiler_config_extra instead

🟡 **L2401** [技术债务]: The modern style is to use CompileId from TracingContext to


### venv/lib/python3.13/site-packages/torch/_inductor/sizevars.py

🟡 **L919** [技术债务]: This is NOT always sound for unbacked symints.  It can

🟡 **L925** [技术债务]: shall we add a runtime assertion at least.

🟡 **L1237** [技术债务]: (jansel): should we use sympy.diff here?


### venv/lib/python3.13/site-packages/torch/_inductor/ir.py

🟡 **L1049** [技术债务]: (chilli): I think it would be better for IRNode to directly set

🟡 **L1524** [技术债务]: this will fail for something like ((1, N) * (N, 1)).sum()

🟡 **L1570** [技术债务]: determine splits when all inputs are broadcast

🟡 **L1843** [技术债务]: should we skip setting these fields for layer2

🟡 **L2110** [技术债务]: (jansel): realize the reduction so we can do dynamic indexing

🟡 **L2610** [技术债务]: Unrolled reduction

🟡 **L2793** [技术债务]: Can combine_fn/reindex close over unbacked symbols? If so, we

🟡 **L2963** [技术债务]: custom splitting heuristic for scan

🟡 **L3836** [技术债务]: These symbols may not escape, if they don't assert so and

🟡 **L4093** [技术债务]: (rec): can this really happen?

🟡 **L5523** [技术债务]: Consider extending tl.dot codegen to support arbitrary loop orders.

🟡 **L6643** [技术债务]: in some cases we sill need to explicitly pass in ordered_kwargs_for_cpp_kernel

🟡 **L6737** [技术债务]: self.kwargs does not always match kwargs defined in schema, so sometimes

🟡 **L7130** [技术债务]: (jansel): impose layout preference on realized buffer

🟡 **L7252** [技术债务]: - Storage to InputBuffer

🟡 **L7366** [技术债务]: move this to the more proper places

🟡 **L7376** [技术债务]: combine this with require_contiguous after

🟡 **L7594** [技术债务]: I can't tell if the symbols here are temporary

🟡 **L7697** [技术债务]: Ideally we should only use at::_ops::randint_low_out::call here,

🟡 **L8792** [技术债务]: when we start compiling in C++20, annotate with [[unlikely]].

🟡 **L10175** [技术债务]: (anijain2305) - Support sym expr as operands in future.

🟡 **L11091** [技术债务]: (yifu): add a pre-grad pass to validate the correctness of collective


### venv/lib/python3.13/site-packages/torch/_inductor/compile_fx_async.py

🟡 **L127** [技术债务]: If the future ended in an exception do we want to continue


### venv/lib/python3.13/site-packages/torch/_inductor/index_propagation.py

🟡 **L359** [技术债务]: Perhaps move this logic to the simplify indexing pass


### venv/lib/python3.13/site-packages/torch/_inductor/constant_folding.py

🟡 **L233** [技术债务]: - more complicated strategy


### venv/lib/python3.13/site-packages/torch/_inductor/virtualized.py

🟡 **L152** [技术债务]: To be honest, I feel we probably should just error in this


### venv/lib/python3.13/site-packages/torch/_inductor/autotune_process.py

🟡 **L1135** [技术债务]: (jgong5): use CppPythonBindingsCodeCache for better binding perf


### venv/lib/python3.13/site-packages/torch/_inductor/utils.py

🟡 **L541** [技术债务]: There is a bug in a call to this function, to repro:

🟡 **L568** [技术债务]: remove when support is added in triton

🟡 **L1567** [技术债务]: Investigate why uint64 tensor creation causes overflow error:

🟡 **L1738** [技术债务]: (rec): or should this be self.__class__(initial_indent=self._indent)?

🟡 **L1989** [技术债务]: we need to properly guard on this global

🟡 **L2566** [技术债务]: Support AOTI for decomposeK

🟡 **L2810** [技术债务]: (jgong5): support dynamic shapes for n or k

🟡 **L2838** [技术债务]: (jgong5): support transposed input

🟡 **L3345** [技术债务]: this is a temporary solution to ensure that we can identify torchrec's

🟡 **L3646** [技术债务]: MPS does not expose streams now

🟡 **L3797** [技术债务]: (voz): It would be nice to enable this assert, but there are lots of tests that

🟡 **L3819** [技术债务]: (voz): Should we always have one anyway?

🟡 **L4011** [技术债务]: remove when support is added in triton

🟡 **L4073** [技术债务]: should remove this op

🟡 **L4533** [技术债务]: change these two configs to default to None and use patch_config


### venv/lib/python3.13/site-packages/torch/_inductor/fuzzer.py

🟡 **L159** [技术债务]: this needs to be indexed to the module, like inductor or dynamo, for name collisions

🟡 **L911** [技术债务]: support more dimensions


### venv/lib/python3.13/site-packages/torch/_inductor/decomposition.py

🟡 **L199** [技术债务]: check if XE4 still need this fallback

🟡 **L367** [技术债务]: Re-enable for mps once our reductions are performant enough

🟡 **L436** [技术债务]: Re-enable for mps once our reductions are performant enough

🟡 **L970** [技术债务]: (aakhundov): replace this (and the above) Any by more


### venv/lib/python3.13/site-packages/torch/_inductor/compile_fx_subproc.py

🟡 **L36** [技术债务]: Do we need to copy across some kind of logging IDs? (ChromiumEventLogger)

🟡 **L40** [技术债务]: This is probably the wrong thing to do long-term - but for now

🟡 **L53** [技术债务]: Consider raising this limit if we start using async w/

🟡 **L69** [技术债务]: In subprocess mode we need to clear the inductor caches.

🟡 **L78** [技术债务]: We probably should be using a separate tmpdir in the worker

🟡 **L82** [技术债务]: We could be less aggressive by keeping a clock which gets

🟡 **L89** [技术债务]: turn off config.fx_graph_async_compile


### venv/lib/python3.13/site-packages/torch/_inductor/scheduler.py

🟡 **L334** [技术债务]: add a cache

🟡 **L343** [技术债务]: Mix order reduction is not supported with cpp_wrapper yet

🟡 **L799** [技术债务]: fold richer profitability/coalescing policy into this guard.

🟡 **L839** [技术债务]: enable nested reduction with cpp wrapper after validating the

🟡 **L873** [技术债务]: teach sizevars to infer Mod(s, G)==0 from Mod(s, s//G)==0

🟡 **L1501** [技术债务]: - would be nice if we could just cache accesses on ReadWrites,

🟡 **L1623** [技术债务]: (voz): Should the pragma be constant somewhere?

🟡 **L1647** [技术债务]: (voz): Ostensibly, we should not need this. But there are cases where C++ codegen does

🟡 **L1712** [技术债务]: Calculate this - it's kinda annoying.

🟡 **L1800** [技术债务]: Figure out what's going on

🟡 **L1923** [技术债务]: (xmfan): find a better heuristic to model FLOPS/latency relationship

🟡 **L2279** [技术债务]: (shunting) if this cause compilation time increase when

🟡 **L5140** [技术债务]: (PaulZhang12): Potentially support recompilation/benchmark for new strides

🟡 **L5290** [技术债务]: support benchmarking epilogue fusion

🟡 **L5437** [技术债务]: Remove this check after all Triton templates support prologue fusion.

🟡 **L5822** [技术债务]: (PaulZhang12): Does not support fusions of templates with

🟡 **L6852** [技术债务]: Don't do loop reordering/reindexing for CPU for now.

🟡 **L7122** [技术债务]: - make configurable per input, for instance, bias can fuse fp32 -> fp16 profitably

🟡 **L7131** [技术债务]: - would be nice to generalize this, however, we would need more explicit

🟡 **L7286** [技术债务]: split cheap score prefiltering from legality if this shows up in

🟡 **L9465** [技术债务]: inputs read on multiple streams should be copied in the


### venv/lib/python3.13/site-packages/torch/_inductor/mkldnn_ir.py

🟡 **L186** [技术债务]: support channels_last for such zero stride input.


### venv/lib/python3.13/site-packages/torch/_inductor/choices.py

🟡 **L160** [技术债务]: (coconutruben): break out flexattention/decode configs into the new retrieval mechanism

🟡 **L289** [技术债务]: deprecate this by migrating users to the new behavior

🟡 **L300** [技术债务]: (coconutruben): remove this once CPP,CK,CUTLASS are supported

🟡 **L406** [技术债务]: (jansel): should this default on for dynamic shapes?

🟡 **L407** [技术债务]: (laith) What if hint(reduction_numel) >= threshold ?

🟡 **L503** [技术债务]: test more hardwares

🟡 **L536** [技术债务]: the best heuristic currently has XBLOCK (corresponding to numel_hint) 128


### venv/lib/python3.13/site-packages/torch/_inductor/comm_analysis.py

🟡 **L465** [技术债务]: (ivankobzarev): Figure out how we can use time estimations,

🟡 **L817** [技术债务]: (ivankobzarev): Temporarily disabled - NCCL estimator returns internal error.

🟡 **L844** [技术债务]: Refactor with estimate_nccl_collective_runtime_nccl_estimator


### venv/lib/python3.13/site-packages/torch/_inductor/compiler_bisector.py

🟡 **L57** [技术债务]: - add cse ?

🟡 **L72** [技术债务]: - add more - fusions ?

🟡 **L548** [技术债务]: graph bisecting is not well composed with lowering


### venv/lib/python3.13/site-packages/torch/_inductor/bounds.py

🟡 **L254** [技术债务]: this is slightly inaccurate because truncdiv operates at integer


### venv/lib/python3.13/site-packages/torch/_inductor/output_code.py

🟡 **L83** [技术债务]: Remove underscores here

🟡 **L108** [技术债务]: Get rid of this

🟡 **L283** [技术债务]: migrate all disable reasons to stack trace, refactor

🟡 **L559** [技术债务]: - ordered set

🟡 **L930** [技术债务]: This could be better if we're ever able to serialize compiled


### venv/lib/python3.13/site-packages/torch/_inductor/freezing.py

🟡 **L46** [技术债务]: (tmanlaibaatar) figure out why this is different

🟡 **L121** [技术债务]: - further restrict cse ? right now needed to dedup aliasing ops


### venv/lib/python3.13/site-packages/torch/_inductor/dependencies.py

🟡 **L576** [技术债务]: (jansel): explore this further normalization

🟡 **L626** [技术债务]: check call sites


### venv/lib/python3.13/site-packages/torch/_inductor/tiling_utils.py

🟡 **L99** [技术债务]: - only need one of these to be solvable to zero

🟡 **L265** [技术债务]: : store type of split/broadcast on fused node itself,

🟡 **L544** [技术债务]: - will the names for all the inputs/outputs accurately

🟡 **L632** [技术债务]: - deduplicate with candidate_tilings

🟡 **L636** [技术债务]: - reason about indirect vars

🟡 **L673** [技术债务]: separate into dataclass that olds mem, dtype, is_write

🟡 **L828** [技术债务]: - if a var is in the middle, such as [n0, n1, n2]

🟡 **L863** [技术债务]: - for strictly pointwise fusions,

🟡 **L866** [技术债务]: - could also prefer index var splits to reduction, better tested


### venv/lib/python3.13/site-packages/torch/utils/_pytree.py

🟡 **L624** [技术债务]: remove this allowance once downstream callers stop calling

🟡 **L645** [技术债务]: change this warning to an error after OSS/internal stabilize

🟡 **L2115** [技术债务]: (angelayi): remove this function after OSS/internal stabilize

🟡 **L2124** [技术债务]: (angelayi): remove this function after OSS/internal stabilize


### venv/lib/python3.13/site-packages/torch/utils/_traceback.py

🟡 **L85** [技术债务]: This creates a temporary file for every frame, but we

🟡 **L177** [技术债务]: Maybe indicate that the traceback was elided?


### venv/lib/python3.13/site-packages/torch/utils/checkpoint.py

🟡 **L857** [技术债务]: we can probably make this check stricter by checking that


### venv/lib/python3.13/site-packages/torch/utils/backend_registration.py

🟡 **L13** [技术债务]: Should use `torch._C._get_privateuse1_backend_name()` to get

🟡 **L187** [技术债务]: mypy doesn't support @property, see: https://github.com/python/mypy/issues/6185


### venv/lib/python3.13/site-packages/torch/utils/dlpack.py

🟡 **L56** [技术债务]: add a typing.Protocol to be able to tell Mypy that only objects with


### venv/lib/python3.13/site-packages/torch/utils/_cxx_pytree.py

🟡 **L263** [技术债务]: (XuehaiPan): remove this condition when we make Python pytree out-of-box support


### venv/lib/python3.13/site-packages/torch/utils/bundled_inputs.py

🟡 **L396** [技术债务]: Should we do this even for non-contiguous tensors?

🟡 **L406** [技术债务]: Provide more useful diagnostics.


### venv/lib/python3.13/site-packages/torch/utils/mkldnn.py

🟡 **L14** [技术债务]: Remove this once ScriptModule supports registering None buffer

🟡 **L55** [技术债务]: Remove this once ScriptModule supports registering None buffer


### venv/lib/python3.13/site-packages/torch/utils/_python_dispatch.py

🟡 **L865** [技术债务]: use func.has_kernel_for_dispatch_key(backend_key)


### venv/lib/python3.13/site-packages/torch/utils/_typing_utils.py

🟡 **L55** [技术债务]: consider folding both these into the above variants with an optional


### venv/lib/python3.13/site-packages/torch/utils/cpp_extension.py

🟡 **L2963** [技术债务]: generalize with_cuda as specific device type.


### venv/lib/python3.13/site-packages/torch/utils/_content_store.py

🟡 **L101** [技术债务]: make storage support buffer protocol so this isn't

🟡 **L110** [技术债务]: factor this into a random utility

🟡 **L153** [技术债务]: offer some sort of non-blocking API to speed things up

🟡 **L158** [技术债务]: consider not using torch.save for this; we don't actually

🟡 **L184** [技术债务]: Support more advanced snapshotting of requires_grad/grad/etc


### venv/lib/python3.13/site-packages/torch/utils/weak.py

🟡 **L23** [技术债务]: make weakref properly thread safe following


### venv/lib/python3.13/site-packages/torch/contrib/_tensorboard_vis.py

🟡 **L147** [技术债务]: handle attrs


### venv/lib/python3.13/site-packages/torch/quantization/fuse_modules.py

🟡 **L10** [技术债务]: These functions are not used outside the `fuse_modules.py`


### venv/lib/python3.13/site-packages/torch/quantization/__init__.py

🟡 **L44** [技术债务]: add quantize_dynamic_fx


### venv/lib/python3.13/site-packages/torch/testing/_comparison.py

🟡 **L344** [技术债务]: Instead of always upcasting to int64, it would be sufficient to cast to the next higher dtype to avoid

🟡 **L856** [技术债务]: Remove this conversion as soon as all operations are supported natively by the MPS backend

🟡 **L1630** [技术债务]: compose all metas into one AssertionError


### venv/lib/python3.13/site-packages/torch/_library/triton.py

🟡 **L442** [技术债务]: https://github.com/pytorch/pytorch/issues/160333


### venv/lib/python3.13/site-packages/torch/_library/infer_schema.py

🟡 **L72** [技术债务]: Once our minimum version is py3.10+ pass `eval_str=True` to


### venv/lib/python3.13/site-packages/torch/_library/custom_ops.py

🟡 **L1037** [技术债务]: Merge this function with torch.amp.autocast_mode._cast, and refactor it


### venv/lib/python3.13/site-packages/torch/_library/utils.py

🟡 **L350** [技术债务]: need to double check the semantics of the "types" argument to torch_dispatch.

🟡 **L360** [技术债务]: check that I got these args correct (in C++, we pass in "0000"??)


### venv/lib/python3.13/site-packages/torch/_library/fake_class_registry.py

🟡 **L205** [技术债务]: add this check at compile time for __obj_flatten__.


### venv/lib/python3.13/site-packages/torch/amp/grad_scaler.py

🟡 **L287** [技术债务]: is there a way to split by device and dtype without appending in the inner loop?


### venv/lib/python3.13/site-packages/torch/jit/_monkeytype_config.py

🟡 **L132** [技术债务]: To remove this check once Union support in TorchScript lands.


### venv/lib/python3.13/site-packages/torch/jit/_decompositions.py

🟡 **L101** [技术债务]: replace torch.sigmoid -> aten.sigmoid


### venv/lib/python3.13/site-packages/torch/jit/_recursive.py

🟡 **L30** [技术债务]: there should be a more principled way of doing this.

🟡 **L305** [技术债务]: We should really error in this case, but its bc-breaking so

🟡 **L325** [技术债务]: We should really error in this case, but its bc-breaking so

🟡 **L406** [技术债务]: could add more detail here. For example, what the user should do

🟡 **L683** [技术债务]: Why skip this? Because @torch.jit._overload_method will

🟡 **L689** [技术债务]: we don't currently do this functions that are recursively


### venv/lib/python3.13/site-packages/torch/jit/_serialization.py

🟡 **L210** [技术债务]: Pretty sure this approach loses ConstSequential status and such


### venv/lib/python3.13/site-packages/torch/jit/_script.py

🟡 **L879** [技术债务]: we don't have _concrete_type set after load(), and in general we lose constant information.

🟡 **L887** [技术债务]: it's possible that the following is confusing:

🟡 **L1043** [技术债务]: MAKE SURE THAT DISABLING WORKS


### venv/lib/python3.13/site-packages/torch/jit/_shape_functions.py

🟡 **L42** [技术债务]: only assertion error is bound in C++ compilation right now

🟡 **L102** [技术债务]: only assertion error is bound in C++ compilation right now

🟡 **L466** [技术债务]: return self

🟡 **L690** [技术债务]: handling of slice

🟡 **L695** [技术债务]: handling of slice

🟡 **L702** [技术债务]: copy ?

🟡 **L762** [技术债务]: look into rewriting with early return and getting loop unrolling to fire

🟡 **L782** [技术债务]: assertions could be expanded with the error messages

🟡 **L1165** [技术债务]: return self

🟡 **L1173** [技术债务]: use slicing when slice optimization has landed

🟡 **L1613** [技术债务]: migrate over all of symbolic_shape_registry_util.cpp


### venv/lib/python3.13/site-packages/torch/jit/_check.py

🟡 **L158** [技术债务]: @ansley: add `Union` once landed


### venv/lib/python3.13/site-packages/torch/jit/frontend.py

🟡 **L390** [技术债务]: more robust handling of recognizing ignore context manager

🟡 **L528** [技术债务]: add input, output validator

🟡 **L784** [技术债务]: try to recover the location of else:? Python doesn't give us useful


### venv/lib/python3.13/site-packages/torch/jit/_builtins.py

🟡 **L137** [技术债务]: add support for more ops


### venv/lib/python3.13/site-packages/torch/jit/_trace.py

🟡 **L161** [技术债务]: figure out one liner to .clone() and set requires_grad

🟡 **L231** [技术债务]: In principle, we track device information in our trace, so it

🟡 **L235** [技术债务]: Consider adding a utility function to torch.jit to test

🟡 **L274** [技术债务]: I'm not sure if the clone here is necessary but it is safer


### venv/lib/python3.13/site-packages/torch/jit/annotations.py

🟡 **L448** [技术债务]: this is hack to recognize NumberType

🟡 **L551** [技术债务]: Consider not exporting these during wildcard import (reserve


### venv/lib/python3.13/site-packages/torch/_dynamo/package.py

🟡 **L587** [技术债务]: save all relevant compilation metrics


### venv/lib/python3.13/site-packages/torch/_dynamo/comptime.py

🟡 **L146** [技术债务]: Maybe complain if this isn't a int/bool/float variable

🟡 **L165** [技术债务]: API for adding a custom guard


### venv/lib/python3.13/site-packages/torch/_dynamo/_trace_wrapped_higher_order_op.py

🟡 **L181** [技术债务]: (jansel): need to ensure this does not get DCEed


### venv/lib/python3.13/site-packages/torch/_dynamo/config.py

🟡 **L249** [技术债务]: (janimesh, voz): Remove both of these flags (or at least guard_nn_modules)

🟡 **L345** [技术债务]: Detect this situation automatically so the user doesn't need


### venv/lib/python3.13/site-packages/torch/_dynamo/guards.py

🟡 **L304** [技术债务]: clarify what fn and attributes guard manager has to get the right things here

🟡 **L984** [技术债务]: - source debug string is probably wrong here.

🟡 **L2275** [技术债务]: (anijain2305) - Delete this when DictGuardManager uses tags

🟡 **L2409** [技术债务]: - Run a CI with the following uncommented to find the remaining places

🟡 **L2442** [技术债务]: (anijain2305) - This is currently restricted to nn.Module objects

🟡 **L2512** [技术债务]: (anijain2305) - Consider this moving this guard to C++

🟡 **L2599** [技术债务]: - Consider moving this to C++ if stable

🟡 **L3003** [技术债务]: (voz): Deduplicate w/ AOTAutograd dupe input guards

🟡 **L3443** [技术债务]: (anijain2305,williamwen42) - Consider moving this to C++.

🟡 **L3506** [技术债务]: (voz): Either populate a dispatch_key check into the guards, or error on users passing in an unsupported

🟡 **L3510** [技术债务]: (voz): We are missing storage offset in all our tensor guards?

🟡 **L4327** [技术债务]: See if we have lift this branch as the first one.

🟡 **L4398** [技术债务]: Be more explicit about the behavior for the users.

🟡 **L4476** [技术债务]: (anijain2305) - Currently this information is stored as an attr on

🟡 **L4488** [技术债务]: (anijain2305, ydwu4) - Skipping export because of following test

🟡 **L4551** [技术债务]: don't do the string rep, do something more structured here

🟡 **L4766** [技术债务]: we could make use of 'DefaultsSource' and offer a .guard.is_defaults() API

🟡 **L4891** [技术债务]: (anijain2305) - There is a duplicate logic in Dynamo to find

🟡 **L4930** [技术债务]: the "guard" here is actually just the top level SHAPE_ENV

🟡 **L5496** [技术债务]: (voz): Combine local and global guard builders.


### venv/lib/python3.13/site-packages/torch/_dynamo/test_minifier_common.py

🟡 **L176** [技术债务]: return a more appropriate data structure here


### venv/lib/python3.13/site-packages/torch/_dynamo/create_parameter_op.py

🟡 **L50** [技术债务]: (jansel): alloc followed by free is inefficient, need a way to allocate an unbacked tensor.


### venv/lib/python3.13/site-packages/torch/_dynamo/aot_compile.py

🟡 **L401** [技术债务]: this should be replaced once we make the backend return the SerializableCallable directly.


### venv/lib/python3.13/site-packages/torch/_dynamo/__init__.py

🟡 **L148** [技术债务]: https://github.com/pytorch/pytorch/issues/139200

🟡 **L193** [技术债务]: https://github.com/pytorch/pytorch/issues/139200


### venv/lib/python3.13/site-packages/torch/_dynamo/types.py

🟡 **L130** [技术债务]: (whc) how do I annotate a _RecordFunction here?


### venv/lib/python3.13/site-packages/torch/_dynamo/bytecode_analysis.py

🟡 **L24** [技术债务]: (lucaskabela): consider moving Instruction into this file

🟡 **L32** [技术债务]: (jansel): double check exception handling


### venv/lib/python3.13/site-packages/torch/_dynamo/resume_execution.py

🟡 **L710** [技术债务]: (jansel): add dead code elimination here


### venv/lib/python3.13/site-packages/torch/_dynamo/output_graph.py

🟡 **L390** [技术债务]: replace `same` function with the one in testing

🟡 **L521** [技术债务]: we should expand this to make it work for atribtrary in/out

🟡 **L702** [技术债务]: maybe should just pass the entire f_code in here?  Not

🟡 **L749** [技术债务]: (tmanlaibaatar) Remove this once we always lift params and buffers

🟡 **L1307** [技术债务]: (rzou): can delete after we refactor speculate_subgraph to use nested GraphTracer.

🟡 **L1536** [技术债务]: `nn_modules` has been historically overloaded to store a lot more

🟡 **L2433** [技术债务]: get debug_locals working for nested graph breaks

🟡 **L2858** [技术债务]: (voz): The way export uses gm, and fake tensors, is not supported with us resetting

🟡 **L2873** [技术债务]: (voz): Ostensibly, this should be scoped and

🟡 **L3021** [技术债务]: we could omit this for objects we create but shouldn't be too much overhead for now

🟡 **L3075** [技术债务]: Why isn't this stored in meta :think:

🟡 **L3220** [技术债务]: We can also technically remove all cases when the input

🟡 **L3241** [技术债务]: I don't think it's possible to have a bare int/float here?

🟡 **L3244** [技术债务]: This will bail here if you ever end up with a more complicated


### venv/lib/python3.13/site-packages/torch/_dynamo/compiled_autograd.py

🟡 **L433** [技术债务]: (jansel): are all these modes needed?

🟡 **L1180** [技术债务]: (yf225): work around: remove dead codes like `sym_size` and `sym_numel` which are not used downstream. e.g.


### venv/lib/python3.13/site-packages/torch/_dynamo/exc.py

🟡 **L274** [技术债务]: make this argument required once we remove Unsupported subclasses

🟡 **L389** [技术债务]: I'm a little uncertain about what error classification we should have


### venv/lib/python3.13/site-packages/torch/_dynamo/utils.py

🟡 **L484** [技术债务]: should we assert that the keys of metadata are in CompilationMetrics?

🟡 **L728** [技术债务]: (masneral): Deprecate this param.

🟡 **L843** [技术债务]: the events that we capture in calculate_time_spent() seem a little

🟡 **L1473** [技术债务]: (anijain2305) - Investigate if we can get rid of this function

🟡 **L1707** [技术债务]: The following are legacy fields, populated from the fields that replace

🟡 **L2112** [技术债务]: log to init/id tlparse after I add support for it

🟡 **L2532** [技术债务]: this is questionable

🟡 **L2943** [技术债务]: Delete this condition when rollout is done.  NB: this

🟡 **L4497** [技术债务]: Check that this is installed

🟡 **L4826** [技术债务]: - This is a temporary situation where we have two versions of


### venv/lib/python3.13/site-packages/torch/_dynamo/side_effects.py

🟡 **L634** [技术债务]: Modify this API so that we preserve type info of

🟡 **L727** [技术债务]: (anijain2305) - Is it possible to remove this specialization?

🟡 **L917** [技术债务]: see if we could prune dead cells - cell pruning information needs to be forwarded

🟡 **L927** [技术债务]: track from all possible sources.

🟡 **L1010** [技术债务]: generalize this so we never need to call `make_cell`.

🟡 **L1424** [技术债务]: generalize this for cells created during inlining.


### venv/lib/python3.13/site-packages/torch/_dynamo/trace_rules.py

🟡 **L3723** [技术债务]: (yanboliang, anijain2305) - There are a few concerns that we should

🟡 **L3958** [技术债务]: Add MethodType.__code__ to typeshed


### venv/lib/python3.13/site-packages/torch/_dynamo/bytecode_transformation.py

🟡 **L1574** [技术债务]: reenable after better understanding how to handle sourceless


### venv/lib/python3.13/site-packages/torch/_dynamo/convert_frame.py

🟡 **L689** [技术债务]: - Running exec generated frame seems propagates f_globals to the

🟡 **L884** [技术债务]: - We want to run preserve_node_meta context manager here, but the CI

🟡 **L1469** [技术债务]: with torch._dynamo.config.patch(generate_pycode=True):

🟡 **L2252** [技术债务]: replace with CompileEventLogger.compilation_metrics

🟡 **L2363** [技术债务]: (williamwen42) Unsupported exn's from tracing are handled and logged by symbolic_convert.py

🟡 **L2447** [技术债务]: mlazos: add support for same args, or record them

🟡 **L2550** [技术债务]: the first condition is not covered by any test


### venv/lib/python3.13/site-packages/torch/_dynamo/testing.py

🟡 **L218** [技术债务]: shouldn't this be f_locals/f_globals from frame?


### venv/lib/python3.13/site-packages/torch/_dynamo/pgo.py

🟡 **L561** [技术债务]: I'm not sure if we should just bong the entire pgo

🟡 **L603** [技术债务]: info versions of these logs that log only once

🟡 **L1008** [技术债务]: use a safe tempfile create to eliminate lock

🟡 **L1080** [技术债务]: don't log this multiple times


### venv/lib/python3.13/site-packages/torch/_dynamo/symbolic_convert.py

🟡 **L863** [技术债务]: maybe should respect DtoH sync intention of users later??

🟡 **L2534** [技术债务]: (dynamo-team): Split this function into two separate functions for

🟡 **L2785** [技术债务]: (anijain2305) - This is not tested .. unable to create a testcase

🟡 **L5879** [技术债务]: mlazos, add support for enabling multiple artifact logs


### venv/lib/python3.13/site-packages/torch/_dynamo/source.py

🟡 **L1350** [技术债务]: can probably write a generic "test this on everything in the chain"


### venv/lib/python3.13/site-packages/torch/_dynamo/eval_frame.py

🟡 **L223** [技术债务]: (pianpwk): subsume this flag with better is_compiling() coverage

🟡 **L785** [技术债务]: a bit awkward to time, this isn't inside of the dynamo compile region

🟡 **L1432** [技术债务]: Ideally we shouldn't need this check because nested

🟡 **L1810** [技术债务]: (voz): Consider making "explain" output alongside a run / part of a run

🟡 **L1816** [技术债务]: (voz): Do we want a decorator for this?

🟡 **L1852** [技术债务]: (voz): We may have instances of `f` that mutate inputs, we should track sideeffects and reject.

🟡 **L1859** [技术债务]: (voz): Do we want a decorator for this?

🟡 **L1919** [技术债务]: (zhxchen17) Also preserve all the user constraints here.

🟡 **L2055** [技术债务]: option to print ALL of the stack traces at once

🟡 **L2465** [技术债务]: (voz): We may have instances of `f` that mutate inputs, we should track sideeffects and reject.


### venv/lib/python3.13/site-packages/torch/_dynamo/debug_utils.py

🟡 **L425** [技术债务]: - Keep this code for now. But, I don't think we will need this.

🟡 **L785** [技术债务]: Support bundling the entire repro into a zip file for ease of

🟡 **L821** [技术债务]: transfer it to the right device?  But failing this

🟡 **L906** [技术债务]: consider ensuring tensor and storage counters line up?

🟡 **L946** [技术债务]: being optional on device is kind of pointless as the default

🟡 **L1025** [技术债务]: this doesn't actually symint atm


### venv/lib/python3.13/site-packages/torch/_dynamo/decorators.py

🟡 **L1285** [技术债务]: Make this configurable via a supported public API

🟡 **L1305** [技术债务]: (voz): Should we bounds check?

🟡 **L1335** [技术债务]: Make this configurable via a supported public API

🟡 **L1341** [技术债务]: (voz): Should we bounds check?

🟡 **L1393** [技术债务]: Make this configurable via a supported public API

🟡 **L1409** [技术债务]: (voz): Should we bounds check?


### venv/lib/python3.13/site-packages/torch/_lazy/__init__.py

🟡 **L16** [技术债务]: (whc) expand this to include backend hooks and align with XLA backend needs


### venv/lib/python3.13/site-packages/torch/_lazy/extract_compiled_graph.py

🟡 **L132** [技术债务]: This solution is no ideal since we may miss some factory methods. In future

🟡 **L189** [技术债务]: this part is TS backend specific for now and will be generalized to


### venv/lib/python3.13/site-packages/torch/_refs/__init__.py

🟡 **L120** [技术债务]: model kwargs

🟡 **L543** [技术债务]: add type promotion support

🟡 **L854** [技术债务]: if this is special maybe it should be defined there and imported here?

🟡 **L1097** [技术债务]: register this as a real ref/decomposition once TorchInductor supports complex!

🟡 **L1762** [技术债务]: skip unnecessary conversion of long to float

🟡 **L1843** [技术债务]: consider refactoring this with add impl

🟡 **L2261** [技术债务]: is_pinned is not currently supported in refs or fake_tensor

🟡 **L2286** [技术债务]: non_blocking should be handled by `copy_to`

🟡 **L2320** [技术债务]: - this is true for eager mode currently, but it's wrong behavior for complex norms

🟡 **L3121** [技术债务]: make logic consistent with aten contiguous

🟡 **L3245** [技术债务]: we could look at directing collapse_view to skip its meta function here (unsafe_collapse_view)

🟡 **L3516** [技术债务]: Adding this as a meta function causes functorch tests to fail when compiled with debug mode.

🟡 **L4820** [技术债务]: Add sparse support

🟡 **L4948** [技术债务]: Turn this into a decomposition (currently fails on reshape meta tests)

🟡 **L5806** [技术债务]: unused

🟡 **L5836** [技术债务]: Use requires_grad.  All refs taking the requires_grad kwarg must

🟡 **L6498** [技术债务]: add support for functionalization aten.normal_functional

🟡 **L6780** [技术债务]: This must return a sparse tensor if the input is sparse, but refs have

🟡 **L6802** [技术债务]: this is inaccurate, we actually test PySequence_Check

🟡 **L6845** [技术债务]: this is inaccurate, we actually test PySequence_Check

🟡 **L6856** [技术债务]: test this

🟡 **L6934** [技术债务]: test for numpy input with PyArray_Check

🟡 **L6972** [技术债务]: (or not): support names kwarg

🟡 **L6984** [技术债务]: use torch.get_default_tensor_type


### venv/lib/python3.13/site-packages/torch/profiler/_memory_profiler.py

🟡 **L163** [技术债务]: (robieta): Move away from load bearing names

🟡 **L307** [技术债务]: (robieta):

🟡 **L1090** [技术债务]: Write a faster serialize (orjson not available in CI)


### venv/lib/python3.13/site-packages/torch/profiler/_pattern_matcher.py

🟡 **L184** [技术债务]: We should also check tensor identities

🟡 **L219** [技术债务]: Check if tensor is reused

🟡 **L446** [技术债务]: We should also check if the loader is bottleneck.


### venv/lib/python3.13/site-packages/torch/profiler/profiler.py

🟡 **L378** [技术债务]: CUDA Graph does not work well with CUPTI teardown.


### venv/lib/python3.13/site-packages/torch/profiler/_utils.py

🟡 **L401** [技术债务]: (dberard) - deprecate / remove workaround for CUDA >= 12, when


### venv/lib/python3.13/site-packages/torch/sparse/semi_structured.py

🟡 **L281** [技术债务]: in the future we can add in padding to support sparse dimensions that aren't perfect multiples

🟡 **L638** [技术债务]: is this proper cuSPARSELt metadata?


### venv/lib/python3.13/site-packages/torch/sparse/_triton_ops.py

🟡 **L100** [技术债务]: investigate if contiguity along other axes than the

🟡 **L1014** [技术债务]: eliminate inner for-loops for efficiency


### venv/lib/python3.13/site-packages/torch/export/exported_program.py

🟡 **L207** [技术债务]: (tmanlaibaatar)https://github.com/pytorch/pytorch/issues/129430

🟡 **L282** [技术债务]: we are silently allowing non-safe(non-functional) ops through a crack

🟡 **L383** [技术债务]: T204030333

🟡 **L433** [技术债务]: (tmanlaibaatar) Ideally run_decomp should just call _non_strict_export

🟡 **L585** [技术债务]: (zhxhchen17) Return the new graph_signature directly.

🟡 **L1035** [技术债务]: unfortunately preserving graph-level metadata is not

🟡 **L1587** [技术债务]: (zhxchen17) Remove this.

🟡 **L1690** [技术债务]: remove this

🟡 **L1698** [技术债务]: (zhxchen17) Formalize this.

🟡 **L1804** [技术债务]: Figure out how to resolve guards containing weight sizes.


### venv/lib/python3.13/site-packages/torch/export/unflatten.py

🟡 **L586** [技术债务]: (zhxchen17) We can register modules ahead of time instead of reorder later.

🟡 **L657** [技术债务]: (suo): untangle this.

🟡 **L970** [技术债务]: support skip connection by inlining the child module.


### venv/lib/python3.13/site-packages/torch/export/__init__.py

🟡 **L357** [技术债务]: For backward compatibility, we support loading a zip file from 2.7. Delete this path in 2.9(?)

🟡 **L373** [技术债务]: change archive version to schema version


### venv/lib/python3.13/site-packages/torch/export/_unlift.py

🟡 **L90** [技术债务]: (tmanlaibaatar)

🟡 **L781** [技术债务]: T206340015

🟡 **L856** [技术债务]: (tmanlaibaatar)


### venv/lib/python3.13/site-packages/torch/export/_trace.py

🟡 **L400** [技术债务]: Figure out why sometimes we have root sometimes we don't.

🟡 **L1013** [技术债务]: (zhxchen17) Revisit if this is needed later.

🟡 **L1067** [技术债务]: unfortunately preserving graph-level metadata and output node's meta


### venv/lib/python3.13/site-packages/torch/export/_swap.py

🟡 **L282** [技术债务]: Handle the duplicate module case


### venv/lib/python3.13/site-packages/torch/export/dynamic_shapes.py

🟡 **L259** [技术债务]: (pianpwk): remove after it's no longer internally breaking

🟡 **L307** [技术债务]: (avik): use sympy value range analysis instead?

🟡 **L328** [技术债务]: (avik): use sympy value range analysis instead?

🟡 **L444** [技术债务]: A better way is needed. Currently we use 't_id' to map the constraint,

🟡 **L791** [技术债务]: (avik): check that shape is indeed a Shape

🟡 **L940** [技术债务]: (avik): raise an error in the future


### venv/lib/python3.13/site-packages/torch/nested/__init__.py

🟡 **L97** [技术债务]: Just use nt.to(layout=layout) when it exists.

🟡 **L338** [技术债务]: switch to as_nested_tensor(tensor) when it is available

🟡 **L450** [技术债务]: Truly support offsets=None at some point?


### venv/lib/python3.13/site-packages/torch/_strobelight/compile_time_profiler.py

🟡 **L173** [技术债务]: use threadlevel meta data to tags to record phases.


### venv/lib/python3.13/site-packages/torch/compiler/__init__.py

🟡 **L552** [技术债务]: Remove this helper once Titan no longer depends on it.


### venv/lib/python3.13/site-packages/torch/distributions/constraint_registry.py

🟡 **L248** [技术债务]: define a bijection for LowerCholeskyTransform


### venv/lib/python3.13/site-packages/torch/distributions/utils.py

🟡 **L25** [技术债务]: Use (*values: *Ts) -> tuple[Tensor for T in Ts] if Mapping-Type is ever added.


### venv/lib/python3.13/site-packages/torch/distributions/kl.py

🟡 **L553** [技术债务]: Add Beta-Laplace KL Divergence

🟡 **L592** [技术债务]: Add ContinuousBernoulli-Laplace KL Divergence

🟡 **L651** [技术债务]: Add Exponential-Laplace KL Divergence

🟡 **L696** [技术债务]: Add Gamma-Laplace KL Divergence

🟡 **L728** [技术债务]: Add Gumbel-Laplace KL Divergence

🟡 **L825** [技术债务]: Add Pareto-Laplace KL Divergence

🟡 **L922** [技术债务]: Uniform-Laplace KL Divergence


### venv/lib/python3.13/site-packages/torch/distributions/uniform.py

🟡 **L35** [技术债务]: allow (loc,scale) parameterization to allow independent constraints.


### venv/lib/python3.13/site-packages/torch/package/package_exporter.py

🟡 **L930** [技术债务]: Once we decide to break serialization FC, we can


### venv/lib/python3.13/site-packages/torch/package/importer.py

🟡 **L80** [技术债务]: I guess we should do copyreg too?


### venv/lib/python3.13/site-packages/torch/package/package_importer.py

🟡 **L272** [技术债务]: Once we decide to break serialization FC, we can

🟡 **L309** [技术债务]: from zdevito:


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/runtime_wrappers.py

🟡 **L439** [技术债务]: (https://github.com/pytorch/pytorch/issues/170986)

🟡 **L675** [技术债务]: discuss on the PR and decide if we want to tr to

🟡 **L1166** [技术债务]: I would love to get rid of this argument, but it's

🟡 **L1547** [技术债务]: Can avoid the zip here too, probably

🟡 **L1662** [技术债务]: instead of arbitrarily removing args, it might be useful to

🟡 **L1676** [技术债务]: (voz): This structure is 1:1, we could consider an alternate structure like

🟡 **L1779** [技术债务]: work out how to setup this assert correctly

🟡 **L1804** [技术债务]: refactor trace_joint

🟡 **L1943** [技术债务]: record more detailed desc information here


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/functional_utils.py

🟡 **L273** [技术债务]: add sparse tensors support to functionalization


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/autograd_cache.py

🟡 **L867** [技术债务]: add args and parameters

🟡 **L1045** [技术债务]: should we use the same field for remote cache time saved for both

🟡 **L1083** [技术债务]: this gets logged implicitly by cache_bypass_reason,


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/descriptors.py

🟡 **L320** [技术债务]: the is_* predicates are a little suspicious because (1) they're not

🟡 **L631** [技术债务]: it's a little dodgy this is differentiable lol, but we do generate


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/graph_capture_wrappers.py

🟡 **L332** [技术债务]: I think this hook can also be eliminated now

🟡 **L472** [技术债务]: ideally we do know this is DifferentiableAOTInput

🟡 **L885** [技术债务]: (ivankobzarev): Support fw and bw mutations for subclasses

🟡 **L1170** [技术债务]: (tmanlaibaatar) revisit this if we ever need to turn on non-strict joint graph export

🟡 **L1266** [技术债务]: can probably do a little more resolution here

🟡 **L1326** [技术债务]: add subclass guards (later PR).


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/schemas.py

🟡 **L445** [技术债务]: doc

🟡 **L707** [技术债务]: This function is only a best effort: there are other fields that may not be cache safe

🟡 **L1191** [技术债务]: types here

🟡 **L1194** [技术债务]: this needs to be generic, parameterized on AOTDescriptor

🟡 **L1257** [技术债务]: We potentially could offer a resumable context manager, where you

🟡 **L1448** [技术债务]: bikeshed on this name


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/utils.py

🟡 **L128** [技术债务]: Please remove soon

🟡 **L571** [技术债务]: (future): there is likely a less brittle way to do this by walking

🟡 **L581** [技术债务]: (future): there is likely a less brittle way to do this, same

🟡 **L624** [技术债务]: better to change to a specific field of custom?


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/collect_metadata_analysis.py

🟡 **L177** [技术债务]: see if we can rewrite this to be more accurate using

🟡 **L804** [技术债务]: I'm pretty sure you don't need a tree_map here


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/aot_autograd_result.py

🟡 **L708** [技术债务]: this isn't exactly right, because cudagraphs needs to be a shared config

🟡 **L738** [技术债务]: this ignores flat_params, which can exist


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/frontend_utils.py

🟡 **L151** [技术债务]: Ensure that this codepath is never exercised from

🟡 **L241** [技术债务]: (mlazos): Revisit if this is still needed. With Dynamo install ID


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/graph_capture.py

🟡 **L185** [技术债务]: Refactor the following code so detach() persists item_memo

🟡 **L304** [技术债务]: replace with AOTDispatchSubclassWrapper once we refactor

🟡 **L454** [技术债务]: should factor this into a separate function for export that always only returns just the graph.

🟡 **L504** [技术债务]: replace with AOTDispatchSubclassWrapper once we refactor

🟡 **L576** [技术债务]: in AOTAutograd, we create metadata like _indices_of_inps_to_detach to detect


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/graph_compile.py

🟡 **L180** [技术债务]: Refactor this

🟡 **L200** [技术债务]: We could test for consistency with fw_metadata, but this is not a

🟡 **L332** [技术债务]: (anijain2305) - Add tensorify_python_scalars to the HOP graph passes.

🟡 **L1007** [技术债务]: invoke_subgraph should track which of its inputs static indices

🟡 **L2105** [技术债务]: we should apply the below "detach inputs if their gradients are statically known to be None"

🟡 **L2636** [技术债务]: technically, AOTAutograd does a *little* bit of post processing work


### venv/lib/python3.13/site-packages/torch/_functorch/_aot_autograd/logging_utils.py

🟡 **L19** [技术债务]: It would be nice to reset the numbering every time aot_id goes

🟡 **L53** [技术债务]: Don't shove the aot_id in here; set it in the context


### venv/lib/python3.13/site-packages/torch/_export/passes/replace_with_hop_pass_util.py

🟡 **L56** [技术债务]: (tmanlaibaatar) Figure out if this is right behaviour

🟡 **L111** [技术债务]: (shangdiy): remove this line, since the export graph can be non-functional


### venv/lib/python3.13/site-packages/torch/_export/passes/constant_folding.py

🟡 **L151** [技术债务]: - more complicated strategy


### venv/lib/python3.13/site-packages/torch/_export/passes/replace_autocast_with_hop_pass.py

🟡 **L65** [技术债务]: check if current auto-cast type is the same as the args of


### venv/lib/python3.13/site-packages/torch/_export/serde/serialize.py

🟡 **L462** [技术债务]: Remove this adjustment when Ed gets rid of fractional ranges

🟡 **L774** [技术债务]: (zhxchen17) Maybe provide a function name helper in FX.

🟡 **L778** [技术债务]: (zhxchen17) Don't catch all here.

🟡 **L819** [技术债务]: create a new tensor_values here, meta might have faketensor info

🟡 **L2240** [技术债务]: Directly serialize exported_program.constants once

🟡 **L2347** [技术债务]: (zhxchen17) Follow up on this.

🟡 **L2358** [技术债务]: (zhxchen17) Don't catch all here.

🟡 **L2926** [技术债务]: (avik): find a better way to keep this collection in sync;

🟡 **L2981** [技术债务]: (pianpwk): if we can clean up unused symbols in range_constraints,

🟡 **L3585** [技术债务]: (zhxchen17) blocked on thrift schema refactor


### venv/lib/python3.13/site-packages/torch/_subclasses/complex_tensor/_core.py

🟡 **L32** [技术债务]: (hameerabbasi): `torch.compile` sometimes fails here without making these

🟡 **L37** [技术债务]: (hameerabbasi):


### venv/lib/python3.13/site-packages/torch/_subclasses/complex_tensor/_ops/prims.py

🟡 **L16** [技术债务]: (hameerabbasi): Not being tested


### venv/lib/python3.13/site-packages/torch/_subclasses/complex_tensor/_ops/common.py

🟡 **L176** [技术债务]: (hameerabbasi): Should there be a `torch.SymComplex`?

🟡 **L343** [技术债务]: (hameerabbasi): Test perf with `_compile` set to `True`


### venv/lib/python3.13/site-packages/torch/_subclasses/complex_tensor/_ops/aten.py

🟡 **L118** [技术债务]: (hameerabbasi): Not being tested

🟡 **L149** [技术债务]: (hameerabbasi): Not being tested

🟡 **L399** [技术债务]: (hameerabbasi): The two lines below may have numerical issues

🟡 **L417** [技术债务]: (hameerabbasi): The line below may have numerical issues

🟡 **L799** [技术债务]: (hameerabbasi): Not being tested

🟡 **L851** [技术债务]: (hameerabbasi): Not being tested

🟡 **L886** [技术债务]: (hameerabbasi): Not being tested


### venv/lib/python3.13/site-packages/torch/nn/attention/bias.py

🟡 **L253** [技术债务]: Flash accepts causal = True and for this particular op it means lower right


### venv/lib/python3.13/site-packages/torch/nn/attention/__init__.py

🟡 **L31** [技术债务]: Consider using this for sdpa regardless of subclasses


### venv/lib/python3.13/site-packages/torch/nn/attention/varlen.py

🟡 **L75** [技术债务]: check this

🟡 **L78** [技术债务]: check this

🟡 **L85** [技术债务]: cuDNN supports per-sequence KV lengths via SEQ_LEN_KV + padding_mask,

🟡 **L356** [技术债务]: look into this


### venv/lib/python3.13/site-packages/torch/nn/attention/flex_attention.py

🟡 **L1992** [技术债务]: remove FORCE_USE_FLEX_ATTENTION once BACKEND is fully adopted.

🟡 **L2044** [技术债务]: support CPU for training and return lse

🟡 **L2061** [技术债务]: support CPU/MPS for returning max


### venv/lib/python3.13/site-packages/torch/nn/parallel/comm.py

🟡 **L141** [技术债务]: When `len(inputs) == 1` and all inputs are on `destination`, just


### venv/lib/python3.13/site-packages/torch/nn/parallel/data_parallel.py

🟡 **L134** [技术债务]: update notes/cuda.rst when this class handles 8+ GPUs well


### venv/lib/python3.13/site-packages/torch/nn/parallel/distributed.py

🟡 **L229** [技术债务]: (rohan-varma): keep_low_precision_grads: bool = False

🟡 **L230** [技术债务]: (rohan-varma): APIs to allow users to run batchnorm and layernorm

🟡 **L287** [技术债务]: Expand to remote RRefs.

🟡 **L435** [技术债务]: make DDP uneven inputs context manager support buffer

🟡 **L875** [技术债务]: This is a temporary work around to enable DDP + TP.

🟡 **L1029** [技术债务]: Remove in the future

🟡 **L1322** [技术债务]: when zero_grad(set_to_none=False) or in grad

🟡 **L1806** [技术债务]: (rohan-varma) test this codepath.

🟡 **L1843** [技术债务]: DDPSink is currently enabled for unused parameter detection and


### venv/lib/python3.13/site-packages/torch/nn/utils/stateless.py

🟡 **L252** [技术债务]: allow kwargs such as unsafe and others for parametrization


### venv/lib/python3.13/site-packages/torch/nn/utils/memory_format.py

🟡 **L78** [技术债务]: expand this to `_ConvNd` when channels_last support is extended

🟡 **L158** [技术债务]: expand this to `_ConvNd` when channels_last support is extended


### venv/lib/python3.13/site-packages/torch/nn/utils/weight_norm.py

🟡 **L25** [技术债务]: Make return type more specific


### venv/lib/python3.13/site-packages/torch/nn/utils/prune.py

🟡 **L1300** [技术债务]: consider removing this check and allowing users to specify


### venv/lib/python3.13/site-packages/torch/nn/utils/rnn.py

🟡 **L210** [技术债务]: Re-enable this check (.type isn't supported in TorchScript)


### venv/lib/python3.13/site-packages/torch/nn/modules/batchnorm.py

🟡 **L188** [技术债务]: if statement only here to tell the jit to skip emitting this when it is None


### venv/lib/python3.13/site-packages/torch/nn/modules/linear.py

🟡 **L146** [技术债务]: fail fast on quantization API usage error, then remove this class

🟡 **L338** [技术债务]: PartialLinear - maybe in sparse?


### venv/lib/python3.13/site-packages/torch/nn/modules/_functions.py

🟡 **L93** [技术债务]: https://github.com/pytorch/pytorch/issues/78656 describes


### venv/lib/python3.13/site-packages/torch/nn/modules/loss.py

🟡 **L2332** [技术债务]: L1HingeEmbeddingCriterion

🟡 **L2333** [技术债务]: MSECriterion weight

🟡 **L2334** [技术债务]: ClassSimplexCriterion


### venv/lib/python3.13/site-packages/torch/nn/modules/activation.py

🟡 **L88** [技术债务]: check in THNN (if inplace == True, then assert value <= threshold)


### venv/lib/python3.13/site-packages/torch/nn/modules/transformer.py

🟡 **L1196** [技术债务]: copy.deepcopy() is not defined on nn.module


### venv/lib/python3.13/site-packages/torch/nn/modules/module.py

🟡 **L2192** [技术债务]: Change `*args` to `*` and remove the corresponding warning in docs when BC allows.

🟡 **L2238** [技术债务]: Remove `args` and the parsing logic when BC allows.


### venv/lib/python3.13/site-packages/torch/nn/modules/conv.py

🟡 **L1394** [技术债务]: Deprecate and remove the following alias `_ConvTransposeMixin`.

🟡 **L1419** [技术债务]: Conv2dLocal

🟡 **L1420** [技术债务]: Conv2dMap

🟡 **L1421** [技术债务]: ConvTranspose2dMap


### venv/lib/python3.13/site-packages/torch/nn/modules/normalization.py

🟡 **L439** [技术债务]: ContrastiveNorm2d

🟡 **L440** [技术债务]: DivisiveNorm2d

🟡 **L441** [技术债务]: SubtractiveNorm2d


### venv/lib/python3.13/site-packages/torch/nn/modules/rnn.py

🟡 **L1652** [技术债务]: remove when jit supports exception flow


### venv/lib/python3.13/site-packages/torch/nn/modules/padding.py

🟡 **L12** [技术债务]: grad_output size asserts in THNN


### venv/lib/python3.13/site-packages/torch/onnx/ops/__init__.py

🟡 **L155** [技术债务]: Parse domain


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/registration.py

🟡 **L144** [技术债务]: (justinchuby): Add @functools.lru_cache(maxsize=None) if lookup time becomes


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/verification.py

🟡 **L227** [技术债务]: Remove `check_shape` option once every shape inconsistent issue is addressed.

🟡 **L407** [技术债务]: remove this and treat mutating model separately. See #77679

🟡 **L492** [技术债务]: (#77679): remove this and treat mutating model separately.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset10.py

🟡 **L744** [技术债务]: (justinchuby): Extract all the cast ops into a helper function.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_helper.py

🟡 **L237** [技术债务]: (justinchuby): Replace insinstance with _is_value once we figure out mypy

🟡 **L363** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L514** [技术债务]: (justinchuby): Only single output is supported for now. We may want to

🟡 **L1427** [技术债务]: (justinchuby): Check if dtype is indeed a int.

🟡 **L2135** [技术债务]: (justinchuby): We need to handle what happens when we call b.op on a node return

🟡 **L2302** [技术债务]: remove these once we support Type's in the JIT IR and we can once again


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py

🟡 **L1123** [技术债务]: (justinchuby): can index be an int and not a value?

🟡 **L1324** [技术债务]: remove this as onnx opset 11 spec allows negative axes

🟡 **L1691** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L1702** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L1756** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L1770** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L2235** [技术债务]: remove this as onnx opset 11 spec allows negative axes

🟡 **L2301** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L2376** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L2912** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L3203** [技术债务]: (justinchuby): Support multiple quantized args in output

🟡 **L3216** [技术债务]: (justinchuby): Support multiple quantized args in output

🟡 **L3841** [技术债务]: (justinchuby): Support multiple quantized args in output

🟡 **L3852** [技术债务]: (justinchuby): Avoid catching Exception.

🟡 **L3868** [技术债务]: (justinchuby): Support multiple quantized args in output

🟡 **L4927** [技术债务]: remove this as onnx opset 11 spec allows negative axes

🟡 **L5338** [技术债务]: If indexing is supported natively in ONNX in future opsets,

🟡 **L6290** [技术债务]: It would be better to export this as a chunk directly, as this is

🟡 **L6351** [技术债务]: (justinchuby): Use a public method in the helper module

🟡 **L6639** [技术债务]: (justinchuby): report correct name for symbolic being executed


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/utils.py

🟡 **L86** [技术债务]: (justinchuby): Remove dependency to this global variable from constant_fold.cpp

🟡 **L1101** [技术债务]: can we simplify this to always return a tuple of Tensor or None?

🟡 **L1276** [技术债务]: (justinchuby): Create a way to check if an op is fully supported.

🟡 **L1776** [技术债务]: Wrap almost identical attrs assignment or comment the difference.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/_experimental.py

🟡 **L14** [技术债务]: (justinchuby): Deprecate and remove this class.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset18.py

🟡 **L146** [技术债务]: (justinchuby): Support multiple quantized args in output

🟡 **L159** [技术债务]: (justinchuby): Support multiple quantized args in output


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset13.py

🟡 **L525** [技术债务]: So far we don"t have a module using this method. We"ll keep


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset17.py

🟡 **L149** [技术债务]: (#145944): add compatibility with align_to_window option.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/fx/_pass.py

🟡 **L41** [技术债务]: Figure out how to retrieve commit hash.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_analysis.py

🟡 **L199** [技术债务]: tensor_meta is None sometimes when the exported program still knows the shape/type


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_capture_strategies.py

🟡 **L46** [技术债务]: Remove the patches once dynamo supports these functions.


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_onnx_program.py

🟡 **L181** [技术债务]: (#151064): Use dlpack when ORT properly supports it

🟡 **L426** [技术债务]: (justinchuby): Allow different inference options


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_building.py

🟡 **L335** [技术债务]: (justinchuby): Cast the ir.Value here if needed

🟡 **L657** [技术债务]: (after torchlib migration): Remove traceable function handling


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_schemas.py

🟡 **L231** [技术债务]: Handle variadic

🟡 **L241** [技术债务]: Use ir_convenience instead to handle int as float

🟡 **L282** [技术债务]: Handle variadic


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_core.py

🟡 **L567** [技术债务]: (justinchuby): Maybe keep it as None?

🟡 **L595** [技术债务]: Log the message here to expose false positives

🟡 **L624** [技术债务]: Get IR function directly when onnxscript is updated

🟡 **L1320** [技术债务]: Decide if we should keep mutated buffers as inputs/outputs

🟡 **L1717** [技术债务]: (justinchuby): The threshold is arbitrary right now


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_registration.py

🟡 **L97** [技术债务]: (justinchuby): Handle arbitrary custom ops

🟡 **L168** [技术债务]: (justinchuby): Remove this once torchlib is migrated to PyTorch


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_testing.py

🟡 **L94** [技术债务]: (justinchuby): Include output names in the error message


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_compat.py

🟡 **L154** [技术债务]: (justinchuby): Support complex inputs with annotations


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_torchlib/_torchlib_registry.py

🟡 **L65** [技术债务]: (justinchuby): Simplify the logic and remove the private attribute


### venv/lib/python3.13/site-packages/torch/_vendor/quack/layout_utils.py

🟡 **L213** [技术债务]: Sm90 FP8


### venv/lib/python3.13/site-packages/torch/_vendor/quack/gemm_base.py

🟡 **L141** [技术债务]: turn this to cp.async instead of direct G2R copy

🟡 **L166** [技术债务]: cp.async wait once we switch to cp.async


### venv/lib/python3.13/site-packages/torch/_vendor/quack/gemm_config.py

🟡 **L81** [技术债务]: Make 128x160 work with 8 warps. It currently makes the accumulator


### venv/lib/python3.13/site-packages/torch/_vendor/quack/gemm_sm90.py

🟡 **L823** [技术债务]: do we need to check if work_tile is valid?


### venv/lib/python3.13/site-packages/torch/cpu/amp/autocast_mode.py

🟡 **L23** [技术债务]: remove this conditional once we stop supporting Python < 3.13

🟡 **L62** [技术债务]: discuss a unified TorchScript-friendly API for autocast


### venv/lib/python3.13/site-packages/torch/distributed/_tensor/__init__.py

🟡 **L15** [技术债务]: _shards_wrapper/_utils here mainly for checkpoint BC, remove them


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/format_utils.py

🟡 **L85** [技术债务]: read on each host, instead of only the coordinator


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/state_dict.py

🟡 **L537** [技术债务]: make this faster.

🟡 **L1076** [技术债务]: check if value is the same if exists.

🟡 **L1545** [技术债务]: correct the state_dict function signature.

🟡 **L1546** [技术债务]: this API is not yet fully tested. Make it private

🟡 **L1600** [技术债务]: correct the load_state_dict function signature.

🟡 **L1601** [技术债务]: this API is not yet fully tested. Make it private


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/_traverse.py

🟡 **L28** [技术债务]: update docstring for traverse.py

🟡 **L186** [技术债务]: add local offset for _local_tensor in print_nested.


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/_sharded_tensor_utils.py

🟡 **L19** [技术债务]: We need to refactor this code.


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/_dedup_tensors.py

🟡 **L33** [技术债务]: add docstring for dedup_tensors


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/filesystem.py

🟡 **L312** [技术债务]: replace with headq

🟡 **L394** [技术债务]: Using the OverlappingCpuLoader with multiple threads creates significant

🟡 **L872** [技术债务]: sort by offset and cache the reading


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/state_dict_saver.py

🟡 **L75** [技术债务]: test returning `save` here instead.


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/state_dict_loader.py

🟡 **L47** [技术债务]: test returning `load` here instead.


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/utils.py

🟡 **L428** [技术债务]: (kumpera) torch.load fails if we wrap with io.BufferedReader

🟡 **L439** [技术债务]: integrate with distributed logging flag


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/default_planner.py

🟡 **L69** [技术债务]: Update docstrings for default_planner.py


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/planner_helpers.py

🟡 **L533** [技术债务]: let state_dict_util._iterate_state_dict() to support in place option


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/optimizer.py

🟡 **L201** [技术债务]: we should change _create_sharded_read_items to have more ergonomic API

🟡 **L357** [技术债务]: the type of planner is wrong in load_state_dict


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/_fsspec_filesystem.py

🟡 **L95** [技术债务]: add the dcp.async_save mixin


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/_nested_dict.py

🟡 **L26** [技术债务]: Update Docstring for nested_dict.py


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/_IR.py

🟡 **L34** [技术债务]: :

🟡 **L569** [技术债务]: is there a way not to hard wire init?

🟡 **L700** [技术债务]: investigate

🟡 **L769** [技术债务]: what does split do with module invocations? does it move the modules

🟡 **L793** [技术债务]: backport this into split_module

🟡 **L877** [技术债务]: handle non-persistent buffer

🟡 **L1109** [技术债务]: ? Not sure yet.


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/_schedule_visualizer.py

🟡 **L117** [技术债务]: later we can change this at the schedule creation level to not use Nones


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/microbatch.py

🟡 **L432** [技术债务]: _debug_mask_minibatches


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/_backward.py

🟡 **L480** [技术债务]: handling requires_grad=False dynamically. Can we analyze this during initial


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/stage.py

🟡 **L323** [技术债务]: this is needed for backward_maybe_with_nosync

🟡 **L1000** [技术债务]: We may want to change our semantics so we are allowed to ignore

🟡 **L1030** [技术债务]: we dont need to save this, add to dw_runner?

🟡 **L1094** [技术债务]: figure out a better way to do this:


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/schedules.py

🟡 **L55** [技术债务]: (whc) rename to _ActType?

🟡 **L220** [技术债务]: make a real 'None action' that prints as empty string and make mypy happy

🟡 **L387** [技术债务]: STATIC mode group communicator warm-up gap

🟡 **L1507** [技术债务]: we can avoid send/recv if the 2 stages are on the same rank.

🟡 **L2033** [技术债务]: assumption that stages only communicate from distances of +1/-1 (no skip connections)

🟡 **L2134** [技术债务]: We are assuming that stage will always receive from stage-1

🟡 **L2169** [技术债务]: We are assuming that stage will always receive from stage+1

🟡 **L2301** [技术债务]: what level of validation should we offer for compute+comms schedule?

🟡 **L2464** [技术债务]: (whc) it's not actually safe to use _batch_p2p here in the uncommon case the model has skip-connections,

🟡 **L2828** [技术债务]: we don't need to always append, after all 1f1b are finished we can stop appending None

🟡 **L3030** [技术债务]: we dont support input/weight backward split with torch.compile

🟡 **L3227** [技术债务]: we dont support input/weight backward split with torch.compile

🟡 **L3413** [技术债务]: we dont support input/weight backward split with torch.compile


### venv/lib/python3.13/site-packages/torch/distributed/optim/named_optimizer.py

🟡 **L315** [技术债务]: (chienchin): This API should be FSDP agnostic and should support

🟡 **L324** [技术债务]: (chienchin): This API should be FSDP agnostic and should support


### venv/lib/python3.13/site-packages/torch/distributed/optim/functional_sgd.py

🟡 **L62** [技术债务]: Once step_param interface is robust, refactor step to call


### venv/lib/python3.13/site-packages/torch/distributed/optim/functional_adagrad.py

🟡 **L64** [技术债务]: no union or any types in TorchScript, make step a scalar tensor instead


### venv/lib/python3.13/site-packages/torch/distributed/optim/apply_optimizer_in_backward.py

🟡 **L74** [技术债务]: Remove these attributes once we have a better way of accessing


### venv/lib/python3.13/site-packages/torch/distributed/optim/optimizer.py

🟡 **L30** [技术债务]: (wanchaol): remove this once we added TorchScript


### venv/lib/python3.13/site-packages/torch/distributed/optim/zero_redundancy_optimizer.py

🟡 **L1580** [技术债务]: Manually add `self.param_groups` if using a functional


### venv/lib/python3.13/site-packages/torch/distributed/_composable/replicate.py

🟡 **L25** [技术债务]: (@fegin): this variable is originally create for testing, we

🟡 **L199** [技术债务]: (fegin): using kwargs is not a good idea if we would like to make

🟡 **L226** [技术债务]: This is a temporary work around to enable DDP + TP.


### venv/lib/python3.13/site-packages/torch/distributed/_composable/contract.py

🟡 **L27** [技术债务]: we can add additional info to RegistryItem to share across APIs. E.g.,

🟡 **L226** [技术债务]: verify that installed distributed paradigms are compatible with


### venv/lib/python3.13/site-packages/torch/distributed/_tools/runtime_estimator.py

🟡 **L161** [技术债务]: also check metadata change on inputs

🟡 **L321** [技术债务]: @sanketpurandare: Flatten tensors by desugaring the tensor subclasses

🟡 **L322** [技术债务]: @sanketpurandare: Add logic for incorporating communication time


### venv/lib/python3.13/site-packages/torch/distributed/_tools/fsdp2_mem_tracker.py

🟡 **L373** [技术债务]: (@sanketpurandare): This will need to be modified after this PR (https://github.com/pytorch/pytorch/pull/127786)


### venv/lib/python3.13/site-packages/torch/distributed/_tools/sac_estimator.py

🟡 **L327** [技术债务]: @sanketpurandare: this heuristic for finding the last non-view non-inplace op

🟡 **L613** [技术债务]: Write a better explanation why this needs to be done


### venv/lib/python3.13/site-packages/torch/distributed/_tools/fake_collectives.py

🟡 **L244** [技术债务]: (@sanketpurandare) - Confirm size computation

🟡 **L249** [技术债务]: (@sanketpurandare) - Confirm size computation

🟡 **L258** [技术债务]: (@sanketpurandare) - Confirm size computation


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_exec_order_utils.py

🟡 **L80** [技术债务]: (awgu): We can broadcast the metadata of rank 0's `all_handles`

🟡 **L214** [技术债务]: (awgu): Since every module has at most one handle in the

🟡 **L219** [技术债务]: (voz): Don't graph break on this - dynamo hates the n1 != n2

🟡 **L245** [技术债务]: (voz): Don't graph break on this - dynamo hates the i1 != i2


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_traversal_utils.py

🟡 **L38** [技术债务]: Add any other composable APIs that are mutually exclusive.

🟡 **L45** [技术债务]: (awgu): We may be able to remove this function if we retired the


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_state_dict_utils.py

🟡 **L142** [技术债务]: need to check if this is always correct for composable FSDP.

🟡 **L438** [技术债务]: Add DTensor state_dict support for LOCAL_STATE_DICT.

🟡 **L500** [技术债务]: Add DTensor state_dict support for LOCAL_STATE_DICT.


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_wrap_utils.py

🟡 **L44** [技术债务]: We may relax this no-nested-wrapping constraint to support manual


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_optim_utils.py

🟡 **L1456** [技术债务]: This solution is not general and only apply to PTD TP solution.

🟡 **L1762** [技术债务]: it is unclear if we need to do the same check with


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_common_utils.py

🟡 **L269** [技术债务]: Move all the attributes to this class to enable typing for

🟡 **L350** [技术债务]: This is a temporary hack for differentiate between code paths.

🟡 **L494** [技术债务]: Remove this hack once DMP + FSDP is not supported.

🟡 **L586** [技术债务]: Remove this hack once DMP + FSDP is not supported.

🟡 **L660** [技术债务]: We need to run this mixed precision ignored module in fp32,

🟡 **L696** [技术债务]: record_stream doesn't work with non-cuda/mtia/xpu tensors

🟡 **L713** [技术债务]: (voz): Extend a dynamo util to answer the above, unify the codepaths here.


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_unshard_param_utils.py

🟡 **L85** [技术债务]: figure out the case for the composable APIs.

🟡 **L100** [技术债务]: figure out the case for the composable APIs.

🟡 **L146** [技术债务]: Rank 0 can broadcast the `FlatParameter` to allow all ranks to


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_runtime_utils.py

🟡 **L597** [技术债务]: Do not use the side stream for tensor copies for now; investigate

🟡 **L801** [技术债务]: Post-backward prefetching does not support the multiple handles

🟡 **L978** [技术债务]: Investigate why `NO_SHARD` breaks correctness when using

🟡 **L1011** [技术债务]: (rohan-varma): For CPU offload, this unfortunately

🟡 **L1144** [技术债务]: This already-resharded check is brittle:


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_init_utils.py

🟡 **L68** [技术债务]: (awgu): Refactor this later

🟡 **L312** [技术债务]: FSDP's contract for buffers is not well-defined. They are

🟡 **L516** [技术债务]: we need to add additional check once we support FSDP + PiPPy.

🟡 **L700** [技术债务]: We may relax this by taking the FSDP instance's wrapped

🟡 **L887** [技术债务]: We need to establish a contract for FSDP and buffers. For now, we

🟡 **L1109** [技术债务]: See how to deprecate!


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_flat_param.py

🟡 **L103** [技术债务]: Define this for now to avoid circular imports. See if we can remove.

🟡 **L1642** [技术债务]: (awgu): Gradient accumulation outside `no_sync()`

🟡 **L1683** [技术债务]: (rohan-varma): test for full precision with keep_low_precision_grads

🟡 **L1692** [技术债务]: (awgu): We should replace these conditional checks to encode

🟡 **L1860** [技术债务]: Change `_unpadded_unsharded_size` if we change the

🟡 **L2379** [技术债务]: If we want to handle shared parameters, we need to re-generate


### venv/lib/python3.13/site-packages/torch/distributed/_local_tensor/_c10d.py

🟡 **L106** [技术债务]: We can handle permutations but the layout inference algorithm will


### venv/lib/python3.13/site-packages/torch/distributed/_symmetric_memory/__init__.py

🟡 **L1971** [技术债务]: this path can be made device-agnostic if `use_mem_pool` is

🟡 **L2175** [技术债务]: other backends' dispatch goes here

🟡 **L2195** [技术债务]: other backends' dispatch goes here


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_decompositions.py

🟡 **L222** [技术债务]: (pianpwk): RuntimeError is raised when redistribution is detected; switch to a custom error type


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_redistribute.py

🟡 **L993** [技术债务]: (zpcore): support discovering submesh to prevent padding when

🟡 **L1105** [技术债务]: (zpcore): handle case 7: _StridedShard() -> Shard() on the same dim

🟡 **L1132** [技术债务]: (zpcore): handle case 9: Shard() -> _StridedShard()

🟡 **L1135** [技术债务]: (zpcore): handle case 10: Partial() -> _StridedShard()

🟡 **L1162** [技术债务]: (zpcore): if the dst_state contains special placement like

🟡 **L1265** [技术债务]: (zpcore): Temporary workaround for backward compatibility where

🟡 **L1406** [技术债务]: extend nested sharding detection to _StridedShard

🟡 **L1497** [技术债务]: (zpcore): Temporary workaround for the case where _StridedShard

🟡 **L1546** [技术债务]: alltoall/permute reshuffling to change device_mesh if they are not the same


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_sharding_prop.py

🟡 **L259** [技术债务]: (laithsakka): unify with optimization_hint API

🟡 **L316** [技术债务]: Currently this only applies to OpStrategy selection. Requires extra


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_collective_utils.py

🟡 **L101** [技术债务]: enable async op for shard_dim_alltoall

🟡 **L140** [技术债务]: Ideally we should use the meta tensor way

🟡 **L201** [技术债务]: Ideally we should use the meta tensor way

🟡 **L345** [技术债务]: see if we need to tweak this or offer a way for user

🟡 **L427** [技术债务]: add alltoall_cost

🟡 **L523** [技术债务]: see if we want to support this once there's cross mesh communication

🟡 **L529** [技术债务]: (zpcore): test placements with _StridedShard if we replace shard_order

🟡 **L556** [技术债务]: (zpcore): Support _StridedShard redistribution. Remove the temporary

🟡 **L564** [技术债务]: (zpcore): test placements with _StridedShard if we replace shard_order


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_api.py

🟡 **L202** [技术债务]: support uneven sharding when global shape/stride not passed, by

🟡 **L206** [技术债务]: See if we need to make this run_check logic

🟡 **L281** [技术债务]: return the redistributed local tensor directly without

🟡 **L285** [技术债务]: backward is also differentiable now, add a test

🟡 **L355** [技术债务]: consider all_gather the local tensors for better debugging

🟡 **L968** [技术债务]: (xilun): address sharding order


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_dtensor_spec.py

🟡 **L243** [技术债务]: (zpcore): split_factor from `view` and `shard order`

🟡 **L419** [技术债务]: the TensorMetadata arises from


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_random.py

🟡 **L47** [技术债务]: Logs way too much

🟡 **L84** [技术债务]: deprecate this API, but also need to ensure we disable broadcast for PP case, and that's currently


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_op_schema.py

🟡 **L269** [技术债务]: upstream this assert to DTensorSpec itself and fill any missing TensorMetas

🟡 **L411** [技术债务]: see if we should merge this with args_spec


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_tp_conv.py

🟡 **L18** [技术债务]: whether there requires data exchange is currently determined by padding


### venv/lib/python3.13/site-packages/torch/distributed/_pycute/int_tuple.py

🟡 **L150** [技术债务]: With all these length asserts, may want to create a zip_strict wrapper.


### venv/lib/python3.13/site-packages/torch/distributed/rpc/backend_registry.py

🟡 **L302** [技术债务]: make async?

🟡 **L379** [技术债务]: add try-except and destroy _agent in all processes if any fails.


### venv/lib/python3.13/site-packages/torch/distributed/nn/api/remote_module.py

🟡 **L254** [技术债务]: We need to change this to rpc.remote, and make it async (see the else branch below).


### venv/lib/python3.13/site-packages/torch/distributed/elastic/rendezvous/etcd_rendezvous.py

🟡 **L166** [技术债务]: look into using weakref here instead.

🟡 **L215** [技术债务]: we should probably handle a few additional errors,

🟡 **L273** [技术债务]: look into using weakref here instead.

🟡 **L333** [技术债务]: there are a few things that fall under this like


### venv/lib/python3.13/site-packages/torch/distributed/elastic/rendezvous/api.py

🟡 **L88** [技术债务]: swap to collectives comms API


### venv/lib/python3.13/site-packages/torch/distributed/elastic/utils/distributed.py

🟡 **L99** [技术债务]: properly map the exceptions in pybind (c10d/init.cpp)


### venv/lib/python3.13/site-packages/torch/distributed/elastic/agent/server/api.py

🟡 **L93** [技术债务]: @kiuk - make entrypoint a required field

🟡 **L534** [技术债务]: BC - specific to static rdzv and can be simplified further

🟡 **L709** [技术债务]: after stopping workers, wait at least monitor_interval*2 for


### venv/lib/python3.13/site-packages/torch/distributed/algorithms/_checkpoint/checkpoint_wrapper.py

🟡 **L278** [技术债务]: Importing inside function to avoid circular import issue between FSDP and


### venv/lib/python3.13/site-packages/torch/distributed/algorithms/ddp_comm_hooks/optimizer_overlap_hooks.py

🟡 **L84** [技术债务]: (rohan-varma): upcast as needed for DDP mixed precision,


### venv/lib/python3.13/site-packages/torch/distributed/algorithms/ddp_comm_hooks/powerSGD_hook.py

🟡 **L601** [技术债务]: The above procedure does two matmul+allreduce steps per iteration --

🟡 **L827** [技术债务]: The above procedure does two matmul+allreduce steps per iteration --


### venv/lib/python3.13/site-packages/torch/distributed/algorithms/_optimizer_overlap/optimizer_overlap.py

🟡 **L76** [技术债务]: register_fsdp once FSDP supports communication hook.


### venv/lib/python3.13/site-packages/torch/distributed/_composable/fsdp/fully_shard.py

🟡 **L1** [技术债务]: For backward compatibility, we are importing the public objects


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_fully_shard/_fsdp_param_group.py

🟡 **L734** [技术债务]: (#181218): open questions on scope.


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_fully_shard/_fsdp_param.py

🟡 **L219** [技术债务]: Remove this padding logic once DTensor pads the local tensor:

🟡 **L264** [技术债务]: Replace the sharded DTensor parameter construction logic with

🟡 **L266** [技术债务]: Simplify the following sharded parameter padding logic after

🟡 **L793** [技术债务]: Prefer this DTensor to be read-only and generalize the

🟡 **L1021** [技术债务]: need to support tensor subclass


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_fully_shard/_fsdp_collectives.py

🟡 **L93** [技术债务]: Remove this, maybe by warning user to perform eager dist init.


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_fully_shard/_fully_shard.py

🟡 **L893** [技术债务]: Remove this padding logic once DTensor pads the local tensor:


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharded_tensor/api.py

🟡 **L453** [技术债务]: make it as a view of out tensor

🟡 **L525** [技术债务]: make this a __torch_function__ op once ShardedTensor becomes a

🟡 **L927** [技术债务]: figure out what the API should behave when some rank have no shard


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharding_spec/api.py

🟡 **L183** [技术债务]: figure out a generic and efficient way to scatter the shards for EnumerableShardingSpec


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharding_spec/chunk_sharding_spec.py

🟡 **L65** [技术债务]: support named dimension


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharded_tensor/_ops/tensor_ops.py

🟡 **L31** [技术债务]: set grad with a ShardedTensor that consists of all local grads


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharding_spec/chunk_sharding_spec_ops/embedding.py

🟡 **L288** [技术债务]: Make the result a PartialTensor.


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharding_spec/chunk_sharding_spec_ops/embedding_bag.py

🟡 **L408** [技术债务]: Make the result a PartialTensor and move the logic below there.


### venv/lib/python3.13/site-packages/torch/distributed/flight_recorder/components/types.py

🟡 **L182** [技术债务]: We need to add a schema for the following

🟡 **L540** [技术债务]: I think this can validly not match,

🟡 **L546** [技术债务]: We need more states for p2p ops.


### venv/lib/python3.13/site-packages/torch/distributed/flight_recorder/components/builder.py

🟡 **L118** [技术债务]: Bug in FR data format? ranks is '[0, 1,...]'

🟡 **L293** [技术债务]: we need to surface a merged collective info like input/output sizes to users.

🟡 **L364** [技术债务]: should there be a way to mark 'mismatches'?


### venv/lib/python3.13/site-packages/torch/distributed/flight_recorder/components/utils.py

🟡 **L160** [技术债务]: can't verify seq_id bc there might have been valid seq deltas between ranks even within a pg.

🟡 **L296** [技术债务]: Need to verify no seq_id deltas for P2P ops.

🟡 **L370** [技术债务]: For now, we only check the correctness of individual collective within a coalesced one in

🟡 **L464** [技术债务]: we need to figure out a better way to handle the case mentioned above.


### venv/lib/python3.13/site-packages/torch/distributed/tensor/experimental/_attention.py

🟡 **L26** [技术债务]: (fegin): add deprecation message once the final interfaces are concluded.


### venv/lib/python3.13/site-packages/torch/distributed/tensor/experimental/_register_sharding.py

🟡 **L96** [技术债务]: handle out variant ops


### venv/lib/python3.13/site-packages/torch/distributed/tensor/experimental/_func_map.py

🟡 **L184** [技术债务]: the current code doesn't consider the uneven sharding case


### venv/lib/python3.13/site-packages/torch/distributed/tensor/parallel/ddp.py

🟡 **L43** [技术债务]: To add perf optimizations to this iterations

🟡 **L103** [技术债务]: To add test cases and ensure that it works for nested modules


### venv/lib/python3.13/site-packages/torch/distributed/tensor/parallel/style.py

🟡 **L102** [技术债务]: figure out dynamo support for instance method and switch this to instance method


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_tensor_ops.py

🟡 **L555** [技术债务]: Ideally we'd like to make sure the output is re-sharded afterwards to keep input sharding.

🟡 **L578** [技术债务]: need to relax the constraint to src

🟡 **L995** [技术债务]: enable in a separate PR along with more extensive validation.


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_conv_ops.py

🟡 **L147** [技术债务]: actually the output_mask is not respected here, we should


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_pointwise_ops.py

🟡 **L113** [技术债务]: move kwargs handling upstream if this works

🟡 **L479** [技术债务]: (pianpwk): add torch.Tag.pointwise to these ops in native_functions.yaml

🟡 **L589** [技术债务]: handle other inductor prims ops that may need DTensor sharding


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_matrix_ops.py

🟡 **L574** [技术债务]: sdpa might be a good candidate for us to explore decomposed sharding propagation


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/single_dim_strategy.py

🟡 **L762** [技术债务]: maybe this could be helped by adding a new 'tag' to the OpOverload?

🟡 **L1016** [技术债务]: is_shard() misses _StridedShard, use spec.num_shards instead.


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/strategy_validation.py

🟡 **L627** [技术债务]: This is too broad. Consider: (1) explicit checks for shard dim


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_common_rules.py

🟡 **L93** [技术债务]: further merge the sharding properly (i.e. reshard one input to replicate)

🟡 **L160** [技术债务]: consider a more advanced heuristic to pick the best sharding


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/utils.py

🟡 **L120** [技术债务]: (zpcore): Confirm if view op can be handle properly or not. Prevent

🟡 **L569** [技术债务]: refactor fused_ops handling so that there are no longer


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_view_ops.py

🟡 **L956** [技术债务]: non-strict (reshape) should allow can_shard_dim = True

🟡 **L1407** [技术债务]: this can be wrong for situations where we have


### venv/lib/python3.13/site-packages/torch/distributed/tensor/experimental/_context_parallel/_attention.py

🟡 **L416** [技术债务]: (fegin): figure out why this is a requirement since SDPA does not have

🟡 **L672** [技术债务]: remove this hardcoding

🟡 **L707** [技术债务]: remove this hardcoding

🟡 **L745** [技术债务]: remove this hardcoding

🟡 **L783** [技术债务]: remove this hardcoding

🟡 **L826** [技术债务]: remove this hardcoding

🟡 **L870** [技术债务]: remove this hardcoding

🟡 **L907** [技术债务]: remove the context parallel strategy from the default propagation

🟡 **L1019** [技术债务]: unregister_cp_sharding_rules(clear_the_cache=True) will cause

🟡 **L1107** [技术债务]: we should explicitly ask users to unsqueeze the batch dim.

🟡 **L1456** [技术债务]: these global variables are going to bite us someday.


### venv/lib/python3.13/site-packages/torch/autograd/_functions/tensor.py

🟡 **L34** [技术债务]: deprecate this


### venv/lib/python3.13/site-packages/torch/fx/experimental/validator.py

🟡 **L404** [技术债务]: Probably OK to relax this and allow lower precision


### venv/lib/python3.13/site-packages/torch/fx/experimental/accelerator_partitioner.py

🟡 **L356** [技术债务]: add different size support for sparse_nn_partition


### venv/lib/python3.13/site-packages/torch/fx/experimental/graph_gradual_typechecker.py

🟡 **L62** [技术债务]: narrow t to TensorType | _DynType once Node.type is narrowed

🟡 **L245** [技术债务]: . We leave it like this till we add a type to represent tensor sizes

🟡 **L408** [技术债务]: narrow params/return to TensorType | _DynType once Node.type is narrowed


### venv/lib/python3.13/site-packages/torch/fx/experimental/sym_node.py

🟡 **L86** [技术债务]: An incomplete list

🟡 **L554** [技术债务]: use the file/line for some useful diagnostic on why a

🟡 **L564** [技术债务]: use the file/line for some useful diagnostic on why a

🟡 **L574** [技术债务]: use the file/line for some useful diagnostic on why a

🟡 **L597** [技术债务]: file/line here is very important, because the assert has been

🟡 **L621** [技术债务]: use the file/line for some useful diagnostic on why a

🟡 **L717** [技术债务]: this probably needs the sizes-strides eval functions

🟡 **L1343** [技术债务]: These could also be done with indicators, maybe it is better

🟡 **L1370** [技术债务]: let C++ also take advantage of this

🟡 **L1537** [技术债务]: consider constant prop here

🟡 **L1596** [技术债务]: consider constant prop here

🟡 **L1716** [技术债务]: Remove the args construction below if a different sentinel is used by FX.

🟡 **L1786** [技术债务]: This is technically hotpath, but in the ideal end state

🟡 **L1900** [技术债务]: Remove eq and other relations from this list.

🟡 **L1916** [技术债务]: remove these


### venv/lib/python3.13/site-packages/torch/fx/experimental/merge_matmul.py

🟡 **L117** [技术债务]: Properly handle aliasing caused by get_attr. For now,


### venv/lib/python3.13/site-packages/torch/fx/experimental/schema_type_annotation.py

🟡 **L63** [技术债务]: can we emit the union of these? What are the implications on TorchScript


### venv/lib/python3.13/site-packages/torch/fx/experimental/symbolic_shapes.py

🟡 **L325** [技术债务]: There's a ref-cycle here (wrapped_f -> cumulative_cache_info

🟡 **L553** [技术债务]: do boolean equality test too, see

🟡 **L694** [技术债务]: Do we still need this logic below?

🟡 **L1062** [技术债务]: Apparently, returning an OrderedSet here breaks

🟡 **L1307** [技术债务]: Determine if this is correct

🟡 **L1380** [技术债务]: DivideByKey needs to test divisibility at runtime!

🟡 **L1778** [技术债务]: relax

🟡 **L1899** [技术债务]: check perf implications of this

🟡 **L2048** [技术债务]: better printing for -oo and oo

🟡 **L2272** [技术债务]: add storage offset and stride symbolic_context

🟡 **L2325** [技术债务]: (voz): Shape env validation

🟡 **L2350** [技术债务]: (voz): consider a weakref to the shape_env here

🟡 **L2595** [技术债务]: remove this try catch (esp for unbacked_only)

🟡 **L2622** [技术债务]: Deduplicate this with torch/_prims_common/__init__.py

🟡 **L3195** [技术债务]: (avik): https://github.com/pytorch/pytorch/issues/101093

🟡 **L4404** [技术债务]: Do something nontrivial when upper_bound is expression

🟡 **L4436** [技术债务]: Shouldn't we install a guard if the symbol is backed?  Or is the

🟡 **L4454** [技术债务]: this does not install a deferred runtime assert yet

🟡 **L4456** [技术债务]: Maybe dedupe this with _maybe_guard_rel?

🟡 **L4471** [技术债务]: Actually, we can support this as long as one of them is a symbol.

🟡 **L5051** [技术债务]: make this configurable from outside symbolic_context; we made a symbolic_context

🟡 **L5056** [技术债务]: This should be DYNAMIC, using DUCK for BC

🟡 **L5513** [技术债务]: storage_offset handling?

🟡 **L6000** [技术债务]: Make this more efficient by binding all the size/stride/offsets

🟡 **L6277** [技术债务]: type this better

🟡 **L6592** [技术债务]: With int_oo, I think this condition is a noop

🟡 **L6951** [技术债务]: maybe it's guaranteed x in is var_to_range?

🟡 **L7007** [技术债务]: We could further canonicalize Eq ordering the lhs and rhs somehow

🟡 **L7148** [技术债务]: try to get rid of CleanDiv since it breaks the invariant that's simplifications of sympy

🟡 **L7186** [技术债务]: speed up sort?

🟡 **L7269** [技术债务]: it would seem that this pass is not necessary given the

🟡 **L7311** [技术债务]: overload for allow_none literal

🟡 **L7411** [技术债务]: in a Dynamo context, having user code, and having the

🟡 **L7509** [技术债务]: Rework all of this, the constraint logic is very

🟡 **L7583** [技术债务]: Should we propagate size-like-ness?

🟡 **L7819** [技术债务]: Maybe trivial solutions for int should also be

🟡 **L8267** [技术债务]: split conjunctions and evaluate them separately

🟡 **L8319** [技术债务]: does this even worked with unbacked :think:

🟡 **L8410** [技术债务]: maybe reconcile this with use of counterfactual hints

🟡 **L8420** [技术债务]: dedupe this with _maybe_evaluate_static

🟡 **L8496** [技术债务]: If we successfully eliminate a symbol via equality, it

🟡 **L8604** [技术债务]: split conjunctions and evaluate them separately

🟡 **L8619** [技术债务]: assert bool(static_expr)

🟡 **L8662** [技术债务]: Do this in a way that avoids recovering the symbol's


### venv/lib/python3.13/site-packages/torch/fx/experimental/_config.py

🟡 **L36** [技术债务]: Perhaps consider allowing unions for the configs below (so you can hit


### venv/lib/python3.13/site-packages/torch/fx/experimental/proxy_tensor.py

🟡 **L721** [技术债务]: This doesn't properly track storages.  A more robust

🟡 **L1136** [技术债务]: maybe constant SymInts should also be allowed?  Not sure if

🟡 **L1172** [技术债务]: we could use types to test this

🟡 **L1629** [技术债务]: inductor lowering for with_effects needs to be updated to propagate

🟡 **L1779** [技术债务]: Make downstream users of this work with OperatorBase

🟡 **L1852** [技术债务]: (tmanlaibaatar): we should systematically couple it with export verifier,

🟡 **L2138** [技术债务]: I'm not sure what the point of this class is; you can just

🟡 **L2169** [技术债务]: handle case where the first character of target is '*'

🟡 **L2575** [技术债务]: (tmanlaibaatar)

🟡 **L2839** [技术债务]: it would be nice to line these up with the names

🟡 **L2882** [技术债务]: We need to explicitly import torch._dynamo before calling dispatch_trace,

🟡 **L2953** [技术债务]: kind of a bad way to do it, should maybe figure out a better way

🟡 **L3069** [技术债务]: this is a legacy name, there is only ever one proxy mode as it's an

🟡 **L3106** [技术债务]: properly compute types


### venv/lib/python3.13/site-packages/torch/fx/experimental/_size_hinting.py

🟡 **L157** [技术债务]: do we need sympy_subs, or just xreplace


### venv/lib/python3.13/site-packages/torch/fx/passes/regional_inductor.py

🟡 **L59** [技术债务]: we should change partition when there are multiple differently


### venv/lib/python3.13/site-packages/torch/fx/passes/split_module.py

🟡 **L386** [技术债务]: currently placeholders/parameters aren't put into random partitions,


### venv/lib/python3.13/site-packages/torch/fx/passes/runtime_assert.py

🟡 **L112** [技术债务]: Request simplification on runtime asserts before emitting them

🟡 **L378** [技术债务]: Remove relaxing assert on unbacked_symint https://github.com/pytorch/pytorch/issues/119689

🟡 **L399** [技术债务]: use ra.msg here, but it's pretty

🟡 **L599** [技术债务]: some CSE when generating these nodes can probably


### venv/lib/python3.13/site-packages/torch/fx/passes/reinplace.py

🟡 **L159** [技术债务]: this should be beefed up to be able to properly re-inplace with:

🟡 **L162** [技术债务]: we should also figure this info out using torchgen.

🟡 **L619** [技术债务]: later, add the optimization for handling `copy_()` calls in the graph.


### venv/lib/python3.13/site-packages/torch/fx/passes/pass_manager.py

🟡 **L218** [技术债务]: (alexbeloi): add constraint management/validation


### venv/lib/python3.13/site-packages/torch/fx/passes/_tensorify_python_scalars.py

🟡 **L24** [技术债务]: refactor

🟡 **L79** [技术债务]: make sure this runs before CPU->CUDA pass for cudagraph friendliness


### venv/lib/python3.13/site-packages/torch/fx/passes/fake_tensor_prop.py

🟡 **L86** [技术债务]: How is it possible that we get a non fake tensor?  We


### venv/lib/python3.13/site-packages/torch/fx/passes/regional_inductor_invoke_subgraph.py

🟡 **L103** [技术债务]: maybe we could change to check

🟡 **L179** [技术债务]: might not need this boxed_nop after we switch to _RegionCompiler


### venv/lib/python3.13/site-packages/torch/fx/experimental/migrate_gradual_types/constraint_generator.py

🟡 **L630** [技术债务]: add the extra check mentioned here:

🟡 **L654** [技术债务]: review this rule; should input = dyn; output = dyn be included here?

🟡 **L808** [技术债务]: we should figure out why there is a key-error here.

🟡 **L1121** [技术债务]: normalize index

🟡 **L1264** [技术债务]: generate add constraints for scalar addition


### venv/lib/python3.13/site-packages/torch/fx/passes/backends/cudagraphs.py

🟡 **L17** [技术债务]: why is submodules passed here

🟡 **L62** [技术债务]: single node partition may be wrong due to the pessimization


### venv/lib/python3.13/site-packages/torch/fx/passes/utils/source_matcher_utils.py

🟡 **L86** [技术债务]: Bypass "torch_fn" when "source_fn_stack" because now "torch_fn" can


### venv/lib/python3.13/site-packages/torch/fx/passes/utils/matcher_utils.py

🟡 **L103** [技术债务]: assert pattern is a connected graph

🟡 **L237** [技术债务]: use a more efficient way to check if gn is matched before: two-way dict


### venv/lib/python3.13/site-packages/torch/fx/passes/utils/fuser_utils.py

🟡 **L161** [技术债务]: do we really need copy the get_attr node into the graph?


### venv/lib/python3.13/site-packages/torch/cuda/amp/autocast_mode.py

🟡 **L24** [技术债务]: remove this conditional once we stop supporting Python < 3.13

🟡 **L63** [技术债务]: discuss a unified TorchScript-friendly API for autocast


### venv/lib/python3.13/site-packages/torch/backends/_nnapi/serializer.py

🟡 **L14** [技术债务]: Add type annotations

🟡 **L15** [技术债务]: Check tensor types for ops

🟡 **L151** [技术债务]: Expose these directly to Python to avoid maintaining this list.

🟡 **L207** [技术债务]: Make this an enum.

🟡 **L242** [技术债务]: Support non-equal-rank broadcast where semantics match.

🟡 **L273** [技术债务]: Handle dilation

🟡 **L1316** [技术债务]: Possibly check scale and zero point.

🟡 **L1318** [技术债务]: Possibly support variable-sized inputs.

🟡 **L1703** [技术债务]: Support this by adding trailing 1 dims.

🟡 **L1741** [技术债务]: Validate ceil_mode semantics.

🟡 **L2101** [技术债务]: Transform at load time to share weights with CPU model.

🟡 **L2150** [技术债务]: Support automatic reshape

🟡 **L2215** [技术债务]: Transform at load time to share weights with CPU model.

🟡 **L2474** [技术债务]: Transform at load time to share weights with CPU model.


### venv/lib/python3.13/site-packages/torch/backends/_nnapi/prepare.py

🟡 **L81** [技术债务]: See if it's possible to use those directly.

🟡 **L96** [技术债务]: See if it's possible to use those directly.

🟡 **L151** [技术债务]: Maybe make these names match the original.


### venv/lib/python3.13/site-packages/torch/masked/maskedtensor/reductions.py

🟡 **L129** [技术债务]: autograd.Function doesn't support kwarg


### venv/lib/python3.13/site-packages/torch/_inductor/analysis/device_info.py

🟡 **L34** [技术债务]: investigate profiler support for tf32 and allow device to report correct number when it's turned on.


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/triton_heuristics.py

🟡 **L721** [技术债务]: (jansel): we should find a way to move this extra compile into the worker process

🟡 **L1776** [技术债务]: When the AOTI C++ launch path gains cuLaunchKernelEx support for

🟡 **L2806** [技术债务]: (jansel): delete this branch in mid-2025

🟡 **L4304** [技术债务]: (paulzhan): Test heuristic on AMD and internal testing

🟡 **L4345** [技术债务]: this may only be beneficial when each iteration of the reduction

🟡 **L4672** [技术债务]: (jansel): add more configs in max_autotune

🟡 **L4792** [技术债务]: (Intel): CUDA uses num_warps = 1 to disable shared memory.


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/halide_helpers.py

🟡 **L37** [技术债务]: :


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/triton_helpers.py

🟡 **L650** [技术债务]: (isuruf): use inline_asm_elementwise here

🟡 **L852** [技术债务]: (jansel): is this needed?


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/autotune_cache.py

🟡 **L368** [技术债务]: Do we need to compute time_taken_ms and encode that somehow?

🟡 **L542** [技术债务]: The autotune cache includes configs_hash in the key. The problem

🟡 **L601** [技术债务]: check cache_dir() vs filename, then strip dirname


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/static_triton_launcher.py

🟡 **L187** [技术债务]: handle nvTmaDesc/CUtensormap

🟡 **L263** [技术债务]: actually, if the args *don't* match, we probably should

🟡 **L307** [技术债务]: can handle grid functions here or in C++, so


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/benchmarking.py

🟡 **L859** [技术债务]: Revisit incorporating launch overhead effects.


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_wrapper_gpu.py

🟡 **L883** [技术债务]: - support subgraph codegen by lifting functions. Check the

🟡 **L927** [技术债务]: This is added because FC. Remove this once the newly added shim symbols,


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/wrapper.py

🟡 **L210** [技术债务]: Move to a well known place

🟡 **L295** [技术债务]: (aakhundov): the sorting below is generally not sufficient, so

🟡 **L2313** [技术债务]: this seems legit, NullLine has no node

🟡 **L2342** [技术债务]: (rec): not used

🟡 **L2746** [技术债务]: this fallback and those below actually will generate possibly

🟡 **L3043** [技术债务]: (aakhundov): add None args to constants, too. currently, this

🟡 **L4021** [技术债务]: need to assert divisibility

🟡 **L4059** [技术债务]: (desertfire) - This function is the old way of supporting

🟡 **L4549** [技术债务]: Uncomment in future. This will be needed to support subgraph

🟡 **L4558** [技术债务]: Uncomment in future. This will be needed to support subgraph


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/triton_utils.py

🟡 **L313** [技术债务]: (voz): These are kinda redundant, if we can solve out statically_known_multiple_of with


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/triton.py

🟡 **L964** [技术债务]: This is wrong, when lhs, rhs > 2**53, Python does a higher

🟡 **L1423** [技术债务]: - register these ops as having divergent dtype

🟡 **L1597** [技术债务]: : track the value of outside of mask region with cse

🟡 **L2659** [技术债务]: even if the strides are not in descending order the strides

🟡 **L3027** [技术债务]: min block size may be too large / introduce redundancy

🟡 **L6318** [技术债务]: - rnumel should be reasonably close to power of 2

🟡 **L6323** [技术债务]: - need more detailed register analysis

🟡 **L6686** [技术债务]: (jansel): if there are constants, we shouldn't bother passing them as args

🟡 **L7295** [技术债务]: (voz): Ostensibly, we should not need this. But there are cases where C++ codegen does

🟡 **L7404** [技术债务]: - would be better as a hook in triton do_bench that reset

🟡 **L7437** [技术债务]: (jansel): scan does not yet work with cooperative reductions


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/mps.py

🟡 **L141** [技术债务]: This is only accurate up to 2**23

🟡 **L231** [技术债务]: Type annotation for other is wrong, it's often float or int

🟡 **L232** [技术债务]: Should it be converted to lambda on MacOS-15+?

🟡 **L373** [技术债务]: Does it rely on undefined behavior?

🟡 **L572** [技术债务]: (NS): Figure out the right balance between optype casts

🟡 **L1131** [技术债务]: (malfet) Figure out how to do it for aoti

🟡 **L1169** [技术债务]: (malfet): Is upper bound inclusive or exclusive?


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/simd.py

🟡 **L1118** [技术债务]: instead of trying to blindly find complicated exprs, we should hoist the

🟡 **L1230** [技术债务]: (jansel): do we need a reshape here?

🟡 **L1294** [技术债务]: This is not exactly right for cases like below:

🟡 **L2283** [技术债务]: do more validation here

🟡 **L3179** [技术债务]: - use split ranges ?

🟡 **L4182** [技术债务]: incorporate exact bitwidth, and read/write

🟡 **L4210** [技术债务]: , add tests, reduction splits if config.triton.tile_reductions

🟡 **L4211** [技术债务]: we should ignore tiny increases in score for extra splits

🟡 **L4286** [技术债务]: - look into, occurs with dynamic shapes often

🟡 **L4373** [技术债务]: enable by default

🟡 **L4433** [技术债务]: These tiling decisions (equality, ordering, divisibility)


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/triton_combo_kernel.py

🟡 **L120** [技术债务]: benchmark the performance when large pointwise nodes combining with others

🟡 **L208** [技术债务]: support combination of kernels with different block dimensions

🟡 **L936** [技术债务]: is it correct to use the first sub kernel's heuristics?


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/memory_planning.py

🟡 **L276** [技术债务]: (jansel): we could try harder here by merging overlapping in space

🟡 **L695** [技术债务]: (jansel): we should support reusing buffers created via ExternKernelAlloc


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_flex_attention_template.py

🟡 **L24** [技术债务]: reuse cpp codegen to generate below pointwise/reduction kernels

🟡 **L1447** [技术债务]: use inductor IR to rewrite those fusions

🟡 **L1453** [技术债务]: make them general for common bmm templates


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_micro_gemm.py

🟡 **L56** [技术债务]: (jgong5): support constant shapes and lds as template args.

🟡 **L883** [技术债务]: add trans_b support for other micro gemms

🟡 **L930** [技术债务]: supports tuning of sub_block_m/sub_block_n

🟡 **L1601** [技术债务]: support float/half input

🟡 **L2230** [技术债务]: (jgong5): allow autotuning on choices of configs


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp.py

🟡 **L1581** [技术债务]: this seems to be dead

🟡 **L2263** [技术债务]: add supports for more data types when needed

🟡 **L2805** [技术债务]: avoid hard-code torch.float

🟡 **L2811** [技术债务]: should we consider load mask here?

🟡 **L3707** [技术债务]: support transposition with mask

🟡 **L3939** [技术债务]: (jgong5): support alternative tiling factors and data types

🟡 **L4831** [技术债务]: (leslie-fang-intel): only enable parallel within all outer loop levels.

🟡 **L5020** [技术债务]: we can extend fusion support with compatible ranges for FusedSchedulerNode

🟡 **L5177** [技术债务]: (jgong5): support pre-op fusion with template

🟡 **L5673** [技术债务]: (voz): Ostensibly, we should not need this. But there are cases where C++ codegen does

🟡 **L5765** [技术债务]: support kernel profile on other platforms

🟡 **L5930** [技术债务]: (jansel): look into chunk size and other schedules


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_wrapper_cpu.py

🟡 **L208** [技术债务]: thread `num_cpu_threads` from inductor_meta (autotune support).

🟡 **L310** [技术债务]: - support subgraph codegen by lifting functions. Check the

🟡 **L556** [技术债务]: this could be auto-generated from a passed-in custom op schema

🟡 **L1803** [技术债务]: handle integer output (e.g., as in attention)

🟡 **L1882** [技术债务]: consider remove "_out" and add missing inplace variants to fallback_ops.py

🟡 **L1901** [技术债务]: update aoti_torch_index_put_out in ir.py to use autogen out version

🟡 **L2040** [技术债务]: assert divisibility here

🟡 **L2130** [技术债务]: Add buf name directly into check_inf_and_nan.

🟡 **L2507** [技术债务]: add AOTI C API for event-based D2H copy synchronization

🟡 **L2627** [技术债务]: (desertfire) - This function is the old way of supporting

🟡 **L3086** [技术债务]: need to support control flow

🟡 **L3738** [技术债务]: not using type_ as the first step of refactoring. Will update this later.

🟡 **L3763** [技术债务]: This happens because type_ is not always properly set to torch.ListType


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/common.py

🟡 **L891** [技术债务]: why are people passing strings to the printer here :think:

🟡 **L1078** [技术债务]: this is wrong

🟡 **L1079** [技术债务]: an easy bandaid is to generate runtime asserts that it's

🟡 **L2596** [技术债务]: (coconutruben): add some central registration to assert on global uniqueness


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/pallas.py

🟡 **L1893** [技术债务]: TMA supports float64 for loading but current JAX Mosaic GPU


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_gemm_template.py

🟡 **L809** [技术债务]: tune the factor here

🟡 **L840** [技术债务]: Decouple the choice of micro-kernel from cache blocking

🟡 **L884** [技术债务]: (jgong5): something to tune?

🟡 **L948** [技术债务]: (jgong5): perhaps use size hint to decide?

🟡 **L1055** [技术债务]: (jgong5): decide proper number of threads per problem size

🟡 **L1359** [技术债务]: Move VNNI weight packing for non-constant tensors into the template,

🟡 **L1453** [技术债务]: (jgong5): for int8 gemm, bias-add is handled outside of gemm template,


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_wrapper_cpu_array_ref.py

🟡 **L60** [技术债务]: - support subgraph codegen by lifting functions. Check the

🟡 **L578** [技术债务]: input shape checking for regular tensor interface as well?

🟡 **L749** [技术债务]: integrate memory planning & stack allocation?

🟡 **L758** [技术债务]: this seems legit, NullLine has no node

🟡 **L1056** [技术债务]: consider remove "_out" and add missing inplace variants to fallback_ops.py

🟡 **L1085** [技术债务]: update aoti_torch_index_put_out in ir.py to use autogen out version


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/halide.py

🟡 **L505** [技术债务]: (jansel): find a better way to do this, builtin % has wrong sign

🟡 **L554** [技术债务]: (jansel): find a better ways to do this, the select-based trick from triton.py didn't work

🟡 **L613** [技术债务]: (jansel): Halide only supports 32-bit indexing, we should error on overflow

🟡 **L643** [技术债务]: (jansel): look into removing the where in the same places triton does

🟡 **L754** [技术债务]: This is NOT always sound for unbacked symints.

🟡 **L758** [技术债务]: shall we add a runtime assertion at least.

🟡 **L918** [技术债务]: (jansel): we should just prevent fusion in cases that hit this

🟡 **L1122** [技术债务]: (jansel): negative offsets

🟡 **L1587** [技术债务]: (jansel): explore other flags, see:

🟡 **L1605** [技术债务]: (jansel): it is unclear if this does anything, since input sizes are still int32

🟡 **L1767** [技术债务]: (jansel): support asserts

🟡 **L1772** [技术债务]: (jansel): support asserts


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_template.py

🟡 **L127** [技术债务]: add c10::ForcedUnroll test to test_aoti_abi_check


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cuda_combined_scheduling.py

🟡 **L128** [技术债务]: remove this when we add epilogue support


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_utils.py

🟡 **L201** [技术债务]: why are people passing strings to the printer here :think:

🟡 **L752** [技术债务]: Add support of fusion when the read of template buffer and the write of epilogue output


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/debug_utils.py

🟡 **L164** [技术债务]: Find a more reliable way to detect kernel args types to print for extern kernel calls


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/nv_universal_gemm.py

🟡 **L29** [技术债务]: (nikhilap): Extend config key for stages/split_k https://github.com/pytorch/pytorch/issues/177578

🟡 **L332** [技术债务]: (nikhilap): Update when nvMatmulHeuristics supports CUTLASS 4


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/triton.py

🟡 **L87** [技术债务]: (rocm-origami): replace these wrappers with public accessors when the

🟡 **L306** [技术债务]: (coconutruben): remove this once mm_plus_mm and tests support scaling

🟡 **L686** [技术债务]: Unify with other gemm patterns, mm_plus_mm currently follows

🟡 **L2439** [技术债务]: (coconutruben): remove this once all tests work

🟡 **L3134** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3154** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3176** [技术债务]: (coconutruben): replace with template.name once templates are importable

🟡 **L3178** [技术债务]: (coconutruben): replace with template.name once templates are importable

🟡 **L3244** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3268** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3298** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3313** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3330** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3346** [技术债务]: (etaf): Design proper exhaustive search space for XPU.

🟡 **L3388** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3403** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3420** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3450** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3465** [技术债务]: (coconutruben): remove this once we have validated exhaustive support

🟡 **L3482** [技术债务]: (coconutruben): remove this once we have validated exhaustive support


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/__init__.py

🟡 **L2** [技术债务]: write a simple glob if there are many heuristics to auto import them in the right order


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/decompose_k.py

🟡 **L38** [技术债务]: (coconutruben): enable decompose k on other devices (xpu, cpu, mps, mtia)


### venv/lib/python3.13/site-packages/torch/_inductor/autoheuristic/autoheuristic.py

🟡 **L132** [技术债务]: (AlnisM): We might want to allow this in the future

🟡 **L168** [技术债务]: (AlnisM): just using the device name for now, but the same GPU model can have different names

🟡 **L251** [技术债务]: Find a nicer way to handle this


### venv/lib/python3.13/site-packages/torch/_inductor/autoheuristic/autoheuristic_utils.py

🟡 **L102** [技术债务]: (AlnisM): there might be a better way to do this


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/post_grad.py

🟡 **L1836** [技术债务]: to support other reductions like sum, would need to skip


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/decomp_comms.py

🟡 **L32** [技术债务]: validate single-Gram fwd/bwd decomposition on a real model.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/decompose_mem_bound_mm.py

🟡 **L20** [技术债务]: need a better strategy for decomposing mm


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/reinplace.py

🟡 **L576** [技术债务]: Using _overlap here causes a several issues.

🟡 **L723** [技术债务]: this logic can be made more precise using _overlap


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/quantization.py

🟡 **L626** [技术债务]: Ensure sum is safe and remove such check, i.e.,


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/split_cat.py

🟡 **L188** [技术债务]: dynamic_shapes with assume_static_by_default=False fails while AOT Autograd tracing.

🟡 **L248** [技术债务]: dynamic_shapes with assume_static_by_default=False fails while AOT Autograd tracing.

🟡 **L1706** [技术债务]: dynamic_shapes with assume_static_by_default=False fails while AOT Autograd tracing.

🟡 **L1753** [技术债务]: dynamic_shapes with assume_static_by_default=False fails while AOT Autograd tracing.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/node_runtime_estimation.py

🟡 **L94** [技术债务]: Consider using a distributed-aware cache or rank-local disk cache


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/overlap_scheduling.py

🟡 **L277** [技术债务]: - skip unbacked, symbolic

🟡 **L1107** [技术债务]: we could consider skipping overlapping for overlapable, unary chains to collectives.

🟡 **L1407** [技术债务]: We previously tracked path compute time and added it back to available

🟡 **L1655** [技术债务]: We could potentially limit compute nodes per overlap time,


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/pre_grad.py

🟡 **L349** [技术债务]: move efficient_conv_bn_eval_pass to the fusions dict too.

🟡 **L545** [技术债务]: support kwargs.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/micro_pipeline_tp.py

🟡 **L615** [技术债务]: explore unifying the _Matmul and _ScaledMatmul approaches to handling reshapes.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/joint_graph.py

🟡 **L125** [技术债务]: - decompose/type promote to avoid this

🟡 **L155** [技术债务]: handle Tensor-Scalar adds, it's a different schema

🟡 **L363** [技术债务]: cat, more indexing

🟡 **L364** [技术债务]: - do on cpu to avoid syncs

🟡 **L501** [技术债务]: - not sure about lossy uint->python value->uint conversions

🟡 **L1112** [技术债务]: the pattern can be updated to support the case that index tensor


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/bucketing.py

🟡 **L804** [技术债务]: - either use torch.cat or make sure inductor foreach codegen

🟡 **L883** [技术债务]: custom ops support list[dtype] input

🟡 **L1014** [技术债务]: custom ops support list[dtype] input


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/mkldnn_fusion.py

🟡 **L1226** [技术债务]: Support dynamic shape case for MKLDNN conv transpose.

🟡 **L1567** [技术债务]: aarch64: enable op fusion for acl once it supports fused operators. Disabling it for now.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/pad_mm.py

🟡 **L297** [技术债务]: - finetune coefficient here. As a reference point, Triton mm model assumes

🟡 **L390** [技术债务]: - see issue https://github.com/pytorch/pytorch/issues/128889

🟡 **L427** [技术债务]: Build a learned model which would be better than this heuristic


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/freezing_patterns.py

🟡 **L60** [技术债务]: remove the need to run fake_tensor_prop on the whole model.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/misc_patterns.py

🟡 **L190** [技术债务]: Add pattern for cvt.rn.bf16x2.ue8m0x2 (e8m0 -> bf16 conversion)


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/mm_common.py

🟡 **L148** [技术债务]: : support block ptr

🟡 **L185** [技术债务]: : support when size = 1


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/mm.py

🟡 **L90** [技术债务]: To get around rocm failures like https://github.com/pytorch/pytorch/actions/runs/13123783322/job/36617154943

🟡 **L376** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L498** [技术债务]: (coconutruben): remove once we deprecate ah

🟡 **L562** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L628** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L759** [技术债务]: (coconturuben): support V.choices.get_mm_configs for sparse_semi_structured_mm

🟡 **L919** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L1006** [技术债务]: (paulzhan): There is no template that exists for bias and TMA

🟡 **L1131** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L1192** [技术债务]: (paulzhan): There is no template that exists for bias and TMA

🟡 **L1349** [技术债务]: is there a cleaner way to ensure aten.mm is always included?


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/bmm.py

🟡 **L189** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that

🟡 **L296** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/conv.py

🟡 **L531** [技术债务]: This does not guard on the stride order decision,

🟡 **L567** [技术债务]: check if it's beneficial to convert Conv1d to Conv2d and then

🟡 **L572** [技术债务]: maybe we can convert weights to channels last just once before

🟡 **L578** [技术债务]: This does not guard on the stride order decision,

🟡 **L1076** [技术债务]: backward weight 3D

🟡 **L1103** [技术债务]: Use the autotune configuration specific to backward convolution.

🟡 **L1131** [技术债务]: backward input 3D

🟡 **L1177** [技术债务]: use_ck_conv_template for bwd conv

🟡 **L1211** [技术债务]: use_ck_conv_template for bwd conv


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/mm_plus_mm.py

🟡 **L132** [技术债务]: (coconutruben): integrate into MMKernelInputs when all callsites use that


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/custom_op.py

🟡 **L394** [技术债务]: Refine this to a better way to more directly preserve strides

🟡 **L1030** [技术债务]: - consider conflicting patches


### venv/lib/python3.13/site-packages/torch/_inductor/package/package.py

🟡 **L124** [技术债务]: (angelayi): We shouldn't need to do this -- miniz should


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutedsl/cutedsl_kernel.py

🟡 **L163** [技术债务]: Additional attributes needed by template system

🟡 **L447** [技术债务]: I think double invoking is fine for this specific hook

🟡 **L491** [技术债务]: this karg really should not be called `triton`

🟡 **L595** [技术债务]: Fallback for common dimension names - should be replaced with proper dtype tracking


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutedsl/cutedsl_scheduling.py

🟡 **L133** [技术债务]: remove when supported


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/rocm/rocm_template.py

🟡 **L24** [技术债务]: unify with the CUDA version


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/rocm/ck_universal_gemm_template.py

🟡 **L797** [技术债务]: when supporting baddbmm


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/nv_universal_gemm/nv_universal_gemm.py

🟡 **L441** [技术债务]: (nikhilap): Enable heuristics for grouped GEMM


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/nv_universal_gemm/nv_universal_gemm_scheduling.py

🟡 **L137** [技术债务]: add support for fusion when needed


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/nv_universal_gemm/nv_universal_gemm_kernel.py

🟡 **L216** [技术债务]: (nikhilap)  We don't use autotune_args like the Triton path


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutlass/python_evt.py

🟡 **L281** [技术债务]: mlazos: relax this, cutlass supports reductions and other ops


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutlass/gemm_template.py

🟡 **L985** [技术债务]: update epilogue functor according to epilogues.

🟡 **L1235** [技术债务]: mlazos remove this by returning buffer metadata from

🟡 **L1578** [技术债务]: size_hint_fn is passed to both create_example_tensors (just for


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutlass/utils.py

🟡 **L95** [技术债务]: (ipiszy): remove this hack when CUTLASS solves Python scripts packaging structure issues.

🟡 **L97** [技术债务]: (mlazos): epilogue visitor tree currently lives in python/cutlass,

🟡 **L259** [技术债务]: these three look dead?


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/auto_chunker/__init__.py

🟡 **L32** [技术债务]: this is just a placeholder for now.


### venv/lib/python3.13/site-packages/torch/_inductor/fx_passes/auto_chunker/applier.py

🟡 **L190** [技术债务]: (shunting) revisit

🟡 **L223** [技术债务]: any better way to do this?

🟡 **L406** [技术债务]: (shunting): do we always uses a fp32 accumulator?


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/flex_gemm/runtime.py

🟡 **L168** [技术债务]: Route this through the flex frontend so validated A/B/C metadata


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/flex/flex_decoding.py

🟡 **L132** [技术债务]: workload evening at runtime for splits fully masked out.

🟡 **L312** [技术债务]: This feels sketchy


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/flex/flex_attention.py

🟡 **L643** [技术债务]: We probably also need a layout constraint?


### venv/lib/python3.13/site-packages/torch/utils/_sympy/functions.py

🟡 **L198** [技术债务]: In Triton, // rounds to zero, but in Python, it is floor division.

🟡 **L1094** [技术债务]: microoptimization is to avoid overflowing into arbitrary precision

🟡 **L1210** [技术债务]: As an indicator, this != 0 implies == 1 (and vice versa).

🟡 **L1249** [技术债务]: Inability to access size-obliviousness sucks: if we have a


### venv/lib/python3.13/site-packages/torch/utils/_sympy/symbol.py

🟡 **L84** [技术债务]: maybe put the assumptions here directly


### venv/lib/python3.13/site-packages/torch/utils/_sympy/reference.py

🟡 **L472** [技术债务]: maybe composite implicit autograd doesn't work here?

🟡 **L501** [技术债务]: https://github.com/pytorch/pytorch/pull/133654


### venv/lib/python3.13/site-packages/torch/utils/_sympy/value_ranges.py

🟡 **L160** [技术债务]: when the bounds have free variables, this may be

🟡 **L713** [技术债务]: We shall assume division is always valid probably.

🟡 **L1031** [技术债务]: We should tighten value ranges

🟡 **L1050** [技术债务]: We should tighten value ranges


### venv/lib/python3.13/site-packages/torch/utils/_sympy/printers.py

🟡 **L219** [技术债务]: Not sure this works with Triton, even when base/exp are integral

🟡 **L473** [技术债务]: This is only accurate up to 2**53

🟡 **L520** [技术债务]: float vs double

🟡 **L640** [技术债务]: dispatch to llrint depending on index type


### venv/lib/python3.13/site-packages/torch/utils/_sympy/interp.py

🟡 **L52** [技术债务]: Dedupe this with SYMPY_INTERP

🟡 **L57** [技术债务]: add CeilDiv (it doesn't appear in the index_expr)

🟡 **L59** [技术债务]: default to some decompositions if the interpreter doesn't have them

🟡 **L75** [技术债务]: hmm?

🟡 **L84** [技术债务]: There is a hazard here, if we have float * float it will

🟡 **L91** [技术债务]: Inductor can generate these, but it's ill-specified which

🟡 **L108** [技术债务]: do the rest of the opaque unary functions...

🟡 **L114** [技术债务]: This is kind of pointless, we shouldn't be generating sympy.sin


### venv/lib/python3.13/site-packages/torch/utils/hipify/cuda_to_hip_mappings.py

🟡 **L3394** [技术债务]: Remove these. They were necessary for Meta-internal builds.

🟡 **L3444** [技术债务]: Remove these. They were necessary for Meta-internal builds.

🟡 **L3448** [技术债务]: Remove CAFFE2_SPECIFIC_MAPPINGS. They were necessary for Meta-internal builds.

🟡 **L3475** [技术债务]: Remove CAFFE2_PATH_MAPPINGS. They were necessary for Meta-internal builds.

🟡 **L3496** [技术债务]: Remove CAFFE2_SPECIFIC_MAPPINGS and CAFFE2_PATH_MAPPINGS. See above.


### venv/lib/python3.13/site-packages/torch/utils/hipify/hipify_python.py

🟡 **L861** [技术债务]: Remove CAFFE2_PATH_MAPPINGS. They were necessary for Meta-internal builds.


### venv/lib/python3.13/site-packages/torch/utils/_debug_mode/_mode.py

🟡 **L409** [技术债务]: check the context manager


### venv/lib/python3.13/site-packages/torch/utils/tensorboard/_pytorch_graph.py

🟡 **L46** [技术债务]: ; Specify a __slots__ for this class or potentially

🟡 **L115** [技术债务]: See if we can remove this in the future

🟡 **L219** [技术债务]: compute correct memory usage and CPU time once

🟡 **L342** [技术债务]: See if we can extract GPU vs CPU information from the PyTorch model


### venv/lib/python3.13/site-packages/torch/utils/tensorboard/summary.py

🟡 **L207** [技术债务]: expose other parameters in the future.


### venv/lib/python3.13/site-packages/torch/utils/tensorboard/writer.py

🟡 **L74** [技术债务]: See if we can remove this in the future if we are


### venv/lib/python3.13/site-packages/torch/utils/model_dump/__init__.py

🟡 **L204** [技术债务]: Undo at least that second hack.  We should support string states.

🟡 **L323** [技术债务]: Handle this case better.  TorchScript ranges are in bytes,

🟡 **L356** [技术债务]: handle errors here and just ignore the file?


### venv/lib/python3.13/site-packages/torch/utils/data/graph.py

🟡 **L22** [技术债务]: (VitalyFedyunin): Make sure it works without dill module installed


### venv/lib/python3.13/site-packages/torch/utils/data/dataloader.py

🟡 **L723** [技术债务]: (https://github.com/pytorch/pytorch/issues/76750)

🟡 **L749** [技术债务]: add limited pickling support for sharing an iterator

🟡 **L1666** [技术债务]: Unfortunately, for Windows, we are missing a worker


### venv/lib/python3.13/site-packages/torch/utils/benchmark/utils/cpp_jit.py

🟡 **L82** [技术债务]: Remove when back testing is no longer required.


### venv/lib/python3.13/site-packages/torch/utils/benchmark/utils/valgrind_wrapper/timer_interface.py

🟡 **L39** [技术债务]: (#105471): Rename the count field

🟡 **L226** [技术债务]: Once 3.7 is the minimum version, type annotate `other` per PEP 563

🟡 **L467** [技术债务]: Figure out if we can use torch.serialization.add_safe_globals here


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_decorator.py

🟡 **L77** [技术债务]: Lambda for picking

🟡 **L192** [技术债务]: :


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_typing.py

🟡 **L227** [技术债务]: When PyTorch drops the support for Python 3.6, it can be converted

🟡 **L284** [技术债务]: the statements below are not reachable by design as there is a bug and typing is low priority for now.

🟡 **L417** [技术债务]: :


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_hook_iterator.py

🟡 **L166** [技术债务]: Add try-except to in-place reduce traceback from the Exception

🟡 **L220** [技术债务]: Simplify the traceback message to skip over `response = gen.send(None)`


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/dataframe/datapipes.py

🟡 **L39** [技术债务]: (VitalyFedyunin): Replacing with TorchArrow only API, as we are dropping pandas as followup

🟡 **L127** [技术债务]: (VitalyFedyunin): Replace with better iterable exception


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/dataframe/dataframes.py

🟡 **L9** [技术债务]: (VitalyFedyunin): Add error when two different traces get combined

🟡 **L55** [技术债务]: (VitalyFedyunin): Extract this list from the DFIterDataPipe registered functions

🟡 **L74** [技术债务]: All operations are shared across entire InitialCapture, need to figure out what if we join two captures

🟡 **L91** [技术债务]: (VitalyFedyunin): Currently can't pickle (why?)

🟡 **L145** [技术债务]: (VitalyFedyunin): Make this calculation thread safe (as currently it updates pointer)

🟡 **L156** [技术债务]: (VitalyFedyunin): Add tests

🟡 **L157** [技术债务]: (VitalyFedyunin): Need to join context if one of them are empty because we used capture

🟡 **L160** [技术债务]: Check if args or kwargs have more than one different context

🟡 **L162** [技术债务]: Allow CaptureA to take context from mock

🟡 **L237** [技术债务]: VitalyFedyunin execute kwargs and maybe nested structures

🟡 **L259** [技术债务]: (VitalyFedyunin): This should be atomic and thread safe

🟡 **L279** [技术债务]: (VitalyFedyunin): Make this calculation thread safe (as currently it updates pointer)


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/iter/fileopener.py

🟡 **L60** [技术债务]: enforce typing for each instance based on mode, otherwise


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/iter/callable.py

🟡 **L143** [技术债务]: (VitalyFedyunin): Verify that item is any sort of batch

🟡 **L145** [技术债务]: (VitalyFedyunin): Compact all batch dataframes into one

🟡 **L164** [技术债务]: (VitalyFedyunin): Add default collation into df_wrapper

🟡 **L178** [技术债务]: (VitalyFedyunin): We can dynamically extract types from the tuple_values here

🟡 **L179** [技术债务]: (VitalyFedyunin): Instead of ignoring mypy error, make sure tuple_names is not empty

🟡 **L234** [技术债务]: (VitalyFedyunin): Replace `Callable[..., Any]` with `Callable[[IColumn], Any]`

🟡 **L235** [技术债务]: (VitalyFedyunin): Replace with `Dict[Union[str, IColumn], Union[Callable, Enum]]`

🟡 **L242** [技术债务]: (VitalyFedyunin): Validate passed dictionary


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/iter/combinatorics.py

🟡 **L114** [技术债务]: Performance optimization


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/utils/decoder.py

🟡 **L379** [技术债务]: xinyu, figure out why Nvidia do this?


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/utils/snapshot.py

🟡 **L7** [技术债务]: Caveats


### venv/lib/python3.13/site-packages/torch/testing/_internal/hop_db.py

🟡 **L119** [技术债务]: (soulitzer)

🟡 **L339** [技术债务]: once HOPs support DTensor inputs, we should also test DTensors

🟡 **L364** [技术债务]: Dynamo would rewrite this op differently


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_nn.py

🟡 **L153** [技术债务]: reference function

🟡 **L160** [技术债务]: (#50743): Figure out the error. "RuntimeError: Unrecognized tensor type ID: Batched"

🟡 **L2531** [技术债务]: (#50743): figure out the error

🟡 **L3361** [技术债务]: compare structure (ensure analytic jacobian has correct shape)

🟡 **L3482** [技术债务]: do this with in-memory files as soon as torch.save will support it

🟡 **L3785** [技术债务]: torch.complex32 when properly supported

🟡 **L3867** [技术债务]: check that criterions don't ignore grad_output


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_fsdp.py

🟡 **L99** [技术债务]: FSDP non-recursive wrapping

🟡 **L1518** [技术债务]: Disable checking the parameters for pure FP16 due to floating


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_optimizers.py

🟡 **L486** [技术债务]: Move out to testing in param_group?

🟡 **L1284** [技术债务]: Move out to testing in param_group?


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_device_type.py

🟡 **L1009** [技术债务]: remove "allow_xpu" option after Intel GPU support all test case instantiate by this function.

🟡 **L2277** [技术债务]: the "all" in the name isn't true anymore for quite some time as we have also have for example XLA and MPS now.


### venv/lib/python3.13/site-packages/torch/testing/_internal/inductor_utils.py

🟡 **L176** [技术债务]: Remove HAS_MPS condition  when `HAS_GPU` includes HAS_MPS


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_distributed.py

🟡 **L234** [技术债务]: (kwen2501): what is the purpose of this decorator?  Tests with this

🟡 **L1196** [技术债务]: we should pipe the exception of the failed subprocess here.

🟡 **L1429** [技术债务]: get test name from kwargs

🟡 **L1548** [技术债务]: figure out a better way to do this


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_methods_invocations.py

🟡 **L1471** [技术债务]: add reduction kwargs

🟡 **L1934** [技术债务]: no layout

🟡 **L1942** [技术债务]: no layout

🟡 **L2313** [技术债务]: add an override for JIT and revert 0. back to 0

🟡 **L3119** [技术债务]: eager and ref impl throw different types of errors

🟡 **L4139** [技术债务]: https://github.com/pytorch/pytorch/issues/85656

🟡 **L4201** [技术债务]: https://github.com/pytorch/pytorch/issues/85656

🟡 **L4340** [技术债务]: https://github.com/pytorch/pytorch/issues/85656

🟡 **L4618** [技术债务]: @krshrimali, once to_numpy method in SampleInput class is modified to take None inputs,

🟡 **L5357** [技术债务]: can't switch `to.device` overload to use positional arguments

🟡 **L8245** [技术债务]: add reference inputs for where(condition) signature

🟡 **L8265** [技术债务]: (rec): shouldn't other_dtype be used two lines below?

🟡 **L9522** [技术债务]: (rec): should diff_v_head_dim be appended to samples?

🟡 **L9579** [技术债务]: (rec): should diff_v_head_dim be appended to samples?

🟡 **L9914** [技术债务]: remove once the issue is resolved

🟡 **L13384** [技术债务]: AssertionError: UserWarning not triggered : Resized a non-empty tensor but did not warn about it.

🟡 **L13386** [技术债务]: AssertionError: RuntimeError not raised : Expected RuntimeError when doing an unsafe cast

🟡 **L13389** [技术债务]: RuntimeError: value cannot be converted to type double without overflow

🟡 **L13414** [技术债务]: update sample inputs with for_inplace_variant kwarg to support this test

🟡 **L13428** [技术债务]: update sample inputs with for_inplace_variant kwarg to support this test

🟡 **L14291** [技术债务]: :

🟡 **L14323** [技术债务]: :

🟡 **L14514** [技术债务]: :

🟡 **L14559** [技术债务]: :

🟡 **L14879** [技术债务]: geqrf can't forward with complex inputs that require grad

🟡 **L15433** [技术债务]: some signatures of median do support out

🟡 **L15442** [技术债务]: some signatures of nanmedian do support out

🟡 **L15451** [技术债务]: some signatures of var_mean do support out

🟡 **L15467** [技术债务]: some signatures of var_mean do support out

🟡 **L15482** [技术债务]: some signatures of std_mean do support out

🟡 **L15496** [技术债务]: some signatures of var_mean do support out

🟡 **L16394** [技术债务]: AssertionError: The values for attribute 'shape' do not match

🟡 **L17580** [技术债务]: AssertionError: False is not true : Tensors failed to compare as equal!

🟡 **L17605** [技术债务]: AssertionError: False is not true : Tensors failed to compare as equal!

🟡 **L17622** [技术债务]: add shape checks

🟡 **L17690** [技术债务]: add shape checks

🟡 **L17695** [技术债务]: investigate nondeterminism

🟡 **L18160** [技术债务]: Need to understand what this is testing and why it doesn't work

🟡 **L18163** [技术债务]: skip this for now since we can't skip on runtime arch support

🟡 **L18210** [技术债务]: Skip because it produces a CUDA illegal memory access for some reason

🟡 **L18212** [技术债务]: mask_type == 2 (LowerRight)

🟡 **L18254** [技术债务]: combine this with the nn.functional.silu OpInfo when

🟡 **L18286** [技术债务]: intentionally misreports dtypes

🟡 **L18288** [技术债务]: numpy reference diverges: Comparing (nan+nanj) and (-0+0j)

🟡 **L18445** [技术债务]: (whc) should not need sample_inputs_func, but without it

🟡 **L18631** [技术债务]: incorrectly tries to pass a rhs scalar

🟡 **L18671** [技术债务]: incorrectly tries to pass a rhs scalar

🟡 **L18794** [技术债务]: :

🟡 **L18992** [技术债务]: Complex values error with: Greatest absolute difference: nan at index

🟡 **L18999** [技术债务]: :

🟡 **L19617** [技术债务]: :

🟡 **L20015** [技术债务]: (@heitorschueroff) update SampleInput to handle such cases

🟡 **L20075** [技术债务]: This should be the following, but the toleranceOverride does not seem to do anything!

🟡 **L20115** [技术债务]: This should be the following, but the toleranceOverride does not seem to do anything!

🟡 **L20161** [技术债务]: (@kshitij12345): Refactor similar to `mvlgamma` entries.

🟡 **L21181** [技术债务]: same as this?

🟡 **L21779** [技术债务]: in the future, 'trapz' should be made a proper alias of 'trapezoid'

🟡 **L22856** [技术债务]: Investigate why more granular skips in the test don't work in CI

🟡 **L22900** [技术债务]: skip this for now since we can't skip on runtime arch support (taken from scaled_dot_product_attention)

🟡 **L22976** [技术债务]: delete this OpInfo once we add meta support for grid_sampler_3d

🟡 **L22995** [技术债务]: Remove grid_sampler_3d tests once `nn.functional.grid_sample` has

🟡 **L23039** [技术债务]: uint8 input returns uint8 instead of bool

🟡 **L23051** [技术债务]: uint8 input returns uint8 instead of bool

🟡 **L23064** [技术债务]: reduces all dimensions when dim=[]

🟡 **L23086** [技术债务]: reduces all dimensions when dim=[]

🟡 **L23153** [技术债务]: count_nonzero does not accept keepdim kwarg

🟡 **L23161** [技术债务]: dim=[] reduces all dimensions

🟡 **L23170** [技术债务]: mean needs 'dim' parameter when using the 'out' overload.

🟡 **L23184** [技术债务]: mean does not support passing keepdim without passing dim

🟡 **L23186** [技术债务]: mean reduces all dimensions when dim=[]

🟡 **L23227** [技术债务]: prod reduces all dimensions when dim=[]

🟡 **L23262** [技术债务]: cannot specify keepdim without dim

🟡 **L23264** [技术债务]: dim=[] reduces all dimensions

🟡 **L23307** [技术债务]: dim=[] reduces all dimensions

🟡 **L23338** [技术债务]: cannot specify keepdim without dim

🟡 **L23340** [技术债务]: dim=[] reduces all dimensions

🟡 **L23378** [技术债务]: dim=[] reduces all dimensions

🟡 **L23403** [技术债务]: prod does not support passing keepdim without passing dim

🟡 **L23405** [技术债务]: prod reduces all dimensions when dim=[]

🟡 **L23408** [技术债务]: prod does not support passing None to dim

🟡 **L23415** [技术债务]: ValueError: The data in MaskedTensor a and Tensor b do not match

🟡 **L23443** [技术债务]: sum does not support passing keepdim without passing dim

🟡 **L23445** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L23478** [技术债务]: nansum reduces all dimensions when dim=[]

🟡 **L23481** [技术债务]: flaky test so skipped instead of xfailed

🟡 **L23900** [技术债务]: CUDA driver API confirmed a leak in

🟡 **L23922** [技术债务]: CUDA driver API confirmed a leak in

🟡 **L24257** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24286** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24318** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24345** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24372** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24401** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24431** [技术债务]: RuntimeError: no _refs support for torch.rand_like

🟡 **L24544** [技术债务]: torch.ops.aten.copy is not in _refs

🟡 **L24633** [技术债务]: copy doesn't have prim refs

🟡 **L25597** [技术债务]: Port this to an UnaryOpInfo

🟡 **L25963** [技术债务]: output 0: meta disagrees with real impl

🟡 **L26098** [技术债务]: output 0: meta disagrees with real impl

🟡 **L26440** [技术债务]: enable dtype-based tolerances in test_ops.py:TestCommon._ref_test_helper

🟡 **L26484** [技术债务]: Uses minimum and clamp

🟡 **L26512** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26520** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26528** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26539** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26583** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26595** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26603** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26611** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26622** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26633** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26644** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26652** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26660** [技术债务]: If self already has the correct dtype and device, then self is

🟡 **L26699** [技术债务]: doesn't support chalf

🟡 **L26712** [技术债务]: doesn't support chalf

🟡 **L26727** [技术债务]: doesn't support chalf

🟡 **L26774** [技术债务]: AssertionError: RuntimeError not raised

🟡 **L27148** [技术债务]: uint8 input returns uint8 instead of bool

🟡 **L27159** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27178** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27196** [技术债务]: uint8 input returns uint8 instead of bool

🟡 **L27206** [技术债务]: count_nonzero does not accept keepdim kwarg

🟡 **L27221** [技术债务]: dim=[] reduces all dimensions

🟡 **L27231** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27248** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27293** [技术债务]: doesn't test out behavior properly for this operator

🟡 **L27295** [技术债务]: mean reduces all dimensions when dim=[]

🟡 **L27347** [技术债务]: doesn't test out behavior properly for this operator

🟡 **L27349** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27370** [技术债务]: reduces all dimensions when dim=[]

🟡 **L27459** [技术债务]: shouldn't check empty results

🟡 **L27489** [技术债务]: should not compare results of empty_like

🟡 **L27558** [技术债务]: should not compare results of empty_like


### venv/lib/python3.13/site-packages/torch/testing/_internal/logging_tensor.py

🟡 **L31** [技术债务]: TensorBase should work

🟡 **L47** [技术债务]: clone storage aliasing


### venv/lib/python3.13/site-packages/torch/testing/_internal/hypothesis_utils.py

🟡 **L132** [技术债务]: Maybe embed the enforced zero_point in the `torch.iinfo`.


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_quantization.py

🟡 **L387** [技术债务]: (future PR): consider combining with skipIfNoQNNPACK,

🟡 **L1258** [技术债务]: make img_data a single example instead of a list

🟡 **L1439** [技术债务]: (rec): shouldn't qconfig be passed to quantize?

🟡 **L1723** [技术债务]: remove this check and define two fuse_modules function on this module

🟡 **L1962** [技术债务]: self.fc should be self.conv

🟡 **L1977** [技术债务]: self.fc should be self.conv

🟡 **L1995** [技术债务]: self.fc should be self.conv

🟡 **L2149** [技术债务]: remove this check and define two fuse_modules function on this module

🟡 **L2731** [技术债务]: remove this check and define two fuse_model function on this module


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_modules.py

🟡 **L345** [技术债务]: (rec): scalar_target is unused, perhaps should be argument to FunctionInput?

🟡 **L375** [技术债务]: Uncomment when negative weights is supported.

🟡 **L1570** [技术债务]: add pos_weight to the definition here and corresponding SampleInputs


### venv/lib/python3.13/site-packages/torch/testing/_internal/jit_metaprogramming_utils.py

🟡 **L687** [技术债务]: delete this list once we make all nn_tests work


### venv/lib/python3.13/site-packages/torch/testing/_internal/dynamo_test_failures.py

🟡 **L106** [技术债务]: due to case sensitivity problems, for now list these files by hand


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_utils.py

🟡 **L149** [技术债务]: Expand this class to handle arbitrary settings in addition to boolean flags?

🟡 **L1655** [技术债务]: Remove PYTORCH_MIOPEN_SUGGEST_NHWC once ROCm officially supports NHWC in MIOpen

🟡 **L3407** [技术债务]: figure out the flaky -1024 anti-leaks on windows. See #8044

🟡 **L3529** [技术债务]: sure looks like we unconditionally initialize the context here

🟡 **L3625** [技术债务]: Remove this; this is grandfathered in because we suppressed errors

🟡 **L4052** [技术债务]: `x` is a sparse view of `v`. Currently rebase_history for

🟡 **L4431** [技术债务]: add args/kwargs for passing to assertEqual (e.g. rtol, atol)

🟡 **L4495** [技术债务]: default this to True

🟡 **L4570** [技术债务]: compose all metas into one AssertionError

🟡 **L4654** [技术债务]: Support context manager interface

🟡 **L5037** [技术债务]: modernize these to be consistent with make_tensor

🟡 **L5078** [技术债务]: consider more complicated noncontiguity schemes

🟡 **L5099** [技术债务]: remove this (prefer make_symmetric_matrices below)

🟡 **L5150** [技术债务]: remove this (prefer make_symmetric_pd_matrices below)

🟡 **L5359** [技术债务]: remove this by updating test suites using it

🟡 **L5368** [技术债务]: remove this by updating test suites using it

🟡 **L5541** [技术债务]: delete this

🟡 **L5549** [技术债务]: move to test_sparse or sparse utils

🟡 **L6202** [技术债务]: (xmfan): even using TemporaryDirectoryName will result in permission error


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_quantized.py

🟡 **L174** [技术债务]: Update all quantization tests to use this decorator.

🟡 **L309** [技术债务]: can the branch floating point comparisons below be done without


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_dist_composable.py

🟡 **L109** [技术债务]: (rec): forward() is not a method, it's a local function inside __init__


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_subclass.py

🟡 **L9** [技术债务]: Move LoggingTensor here.


### venv/lib/python3.13/site-packages/torch/testing/_internal/jit_utils.py

🟡 **L535** [技术债务]: check gradients for parameters, not just inputs

🟡 **L691** [技术债务]: (suo) remove

🟡 **L755** [技术债务]: Remove me once https://bugs.python.org/issue42666 is resolved

🟡 **L829** [技术债务]: find better way to standardize on op registration itself..


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/core.py

🟡 **L745** [技术债务]: Warn if used

🟡 **L751** [技术债务]: After migration, start adding warnings here

🟡 **L806** [技术债务]: rename this to supports_bwgrad_bwgrad to be consistent with below

🟡 **L901** [技术债务]: rename supports_sparse to supports_sparse_coo

🟡 **L1761** [技术债务]: (@heitorschueroff) Once all reduction operators are using

🟡 **L1765** [技术债务]: (@heitorschueroff) Once all reduction operators are using ReductionOpInfo

🟡 **L2792** [技术债务]: in the future generalize the reference generators to handle n-ary elementwise operations


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/refs.py

🟡 **L54** [技术债务]: add a check for alias coverage

🟡 **L56** [技术债务]: add a check for inplace coverage


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/distributed_test.py

🟡 **L1611** [技术债务]: now that nccl send/recv is supported, there does not seem to

🟡 **L2611** [技术债务]: move this test to use torch.profiler once kineto issues are

🟡 **L3657** [技术债务]: Instead we should probably go through _rank_not_in_group

🟡 **L5307** [技术债务]: Add testing for gloo/CUDA

🟡 **L6598** [技术债务]: NCCL backend does not work correctly for bitwise reduction ops

🟡 **L8736** [技术债务]: enable this for general training use cases:

🟡 **L8968** [技术债务]: (#54879): Provide ability to wait and report all failed ranks


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/signal.py

🟡 **L303** [技术债务]: same as this?


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/_masked.py

🟡 **L161** [技术债务]: for now reductions with non-zero reduction identity and

🟡 **L471** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L710** [技术债务]: amax reduces all dimensions when dim=[]

🟡 **L764** [技术债务]: amax reduces all dimensions when dim=[]

🟡 **L891** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L997** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L1041** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L1141** [技术债务]: sum reduces all dimensions when dim=[]

🟡 **L1278** [技术债务]: :

🟡 **L1365** [技术债务]: reduces all dimensions when dim=[]

🟡 **L1382** [技术债务]: :


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/linalg.py

🟡 **L1499** [技术债务]: backward uses in-place operations that vmap doesn't like

🟡 **L2833** [技术债务]: is this really needed?


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/fft.py

🟡 **L98** [技术债务]: Causes floating point exception on ROCm

🟡 **L290** [技术债务]: errors are too large; needs investigation

🟡 **L826** [技术债务]: :


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/special.py

🟡 **L41** [技术债务]: Consolidate `i0e` with sample_inputs_unary when `make_tensor`,


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/nested.py

🟡 **L337** [技术债务]: look in kwargs too?

🟡 **L711** [技术债务]: Cover this in the set of error inputs

🟡 **L774** [技术债务]: Reducing on ragged dim and non-batch dim is not supported;

🟡 **L858** [技术债务]: write this!

🟡 **L868** [技术债务]: write this!

🟡 **L873** [技术债务]: write this!

🟡 **L878** [技术债务]: write this!

🟡 **L917** [技术债务]: add Tensor case

🟡 **L973** [技术债务]: (need factory functions):

🟡 **L1091** [技术债务]: (need factory functions):

🟡 **L1400** [技术债务]: Handle this with error_inputs

🟡 **L1443** [技术债务]: Handle these via error_inputs.

🟡 **L1466** [技术债务]: Handle this with error_inputs

🟡 **L1604** [技术债务]: Translate the rest of the OpInfos


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/_tensor/common_dtensor.py

🟡 **L826** [技术债务]: if users want to enable testing across hosts, we may need

🟡 **L847** [技术债务]: dist.barrier deadlocks with multiple threads and NCCL: https://github.com/pytorch/pytorch/issues/95895

🟡 **L849** [技术债务]: can't use the above all_reduce as it causes hangs on bionic and focal. It hangs:

🟡 **L987** [技术债务]: dist tensor need to support quantized and sparse

🟡 **L1026** [技术债务]: add multi mesh choices

🟡 **L1292** [技术债务]: (zpcore): remove once the native redistribute supports shard_order arg

🟡 **L1329** [技术债务]: (zpcore): remove once the native distribute_tensor supports

🟡 **L1355** [技术债务]: (zpcore): remove once the native redistribute supports shard_order arg


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/rpc/dist_autograd_test.py

🟡 **L1543** [技术债务]: , need more investigation


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/rpc/tensorpipe_rpc_agent_test_fixture.py

🟡 **L22** [技术债务]: Once we consolidate the error messages returned by the


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/rpc/rpc_test.py

🟡 **L567** [技术债务]: use torch.futures.collect_all

🟡 **L1393** [技术债务]: with TCP init, rank 0 raises Address already in use because

🟡 **L3422** [技术债务]: enable timeouts for rpc.remote/RRef (https://github.com/pytorch/pytorch/issues/33803)

🟡 **L4580** [技术债务]: Merge this test with the corresponding one in RpcTest.

🟡 **L4601** [技术债务]: Merge this test with the corresponding one in RpcTest.

🟡 **L4626** [技术债务]: Merge this test with the corresponding one in RpcTest.

🟡 **L4659** [技术债务]: We wait until the remote completed creating the OwnerRRef

🟡 **L4712** [技术债务]: We wait until the remote completed creating the OwnerRRef

🟡 **L5004** [技术债务]: Cuda RPC is failing due to:


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/nn/api/remote_module_test.py

🟡 **L721** [技术债务]: Once the RPC backend can support directly sending GPU tensors, the expected device type should be "cuda:0".

🟡 **L727** [技术债务]: Once the RPC backend can support directly sending GPU tensors, the expected device type should be "cuda:0".

🟡 **L753** [技术债务]: Once the RPC backend can support directly sending GPU tensors, the expected device type should be "cuda:0".


### venv/lib/python3.13/site-packages/torch/testing/_internal/distributed/rpc/jit/rpc_test.py

🟡 **L930** [技术债务]: , need more investigation

🟡 **L1153** [技术债务]: Can't get a reliable time for this profiling event since


### venv/lib/python3.13/site-packages/torch/_dynamo/backends/distributed.py

🟡 **L161** [技术债务]: add split id to CompileId: https://github.com/pytorch/tlparse/pull/83/files#r1880649384

🟡 **L224** [技术债务]: (whc)

🟡 **L341** [技术债务]: - better way of doing this?


### venv/lib/python3.13/site-packages/torch/_dynamo/backends/onnxrt.py

🟡 **L17** [技术债务]: update test/dynamo/test_backends.py to call is_onnxrt_backend_supported()


### venv/lib/python3.13/site-packages/torch/_dynamo/backends/cudagraphs.py

🟡 **L87** [技术债务]: not correct for args that contain tensors in a struct

🟡 **L93** [技术债务]: error on unrecognized nodes


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/functions.py

🟡 **L389** [技术债务]: (guilhermeleobas): this check should go through fn.__dict__ first as

🟡 **L591** [技术债务]: putting this here to avoid duplication, because we could hit this

🟡 **L603** [技术债务]: (anijain2305) - Replace directly calling UserFunctionVariable with

🟡 **L694** [技术债务]: refactor these 3 branches.

🟡 **L716** [技术债务]: figure out why source isn't available here, and whether

🟡 **L1349** [技术债务]: seems like this should send None


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/iter.py

🟡 **L297** [技术债务]: (dynamo-team): Missing `times` argument handling


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/misc.py

🟡 **L807** [技术债务]: support an expression form as well

🟡 **L1397** [技术债务]: change to Ts = TypeVarTuple("Ts") for py 3.11+

🟡 **L1881** [技术债务]: Add all the functions that go from constants to constants to can_constant_fold_through


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/invoke_subgraph.py

🟡 **L528** [技术债务]: (anijain2305): vLLM workaround -- skip CONSTANT_MATCH on

🟡 **L1235** [技术债务]: (anijain2305) - Collect issues why this does not work for export,


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/lists.py

🟡 **L212** [技术债务]: (dynamo-team): Replace iter_contains by a proper impl. once we

🟡 **L1593** [技术债务]: (guilhermeleobas): Replace this by a proper DequeIteratorVariable


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/torch_function.py

🟡 **L687** [技术债务]: move this logic into `TensorVariable`, or try to merge it


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/user_defined.py

🟡 **L706** [技术债务]: (tp_descr_get) - Comparison dunders must be checked before

🟡 **L753** [技术债务]: (tp_descr_get) - C-level descriptors not matched above (e.g.

🟡 **L1240** [技术债务]: (voz): These can invoke user code!

🟡 **L1243** [技术债务]: (voz): These can invoke user code!

🟡 **L1606** [技术债务]: arguably, this should route to wrap_symint/wrap_symfloat

🟡 **L1738** [技术债务]: else try reconstructing the object by, e.g., leveraging side

🟡 **L2305** [技术债务]: missing method_is_overloaded

🟡 **L2673** [技术债务]: (jansel): add a guard to check for monkey patching?

🟡 **L3113** [技术债务]: (guilhermeleobas): This can trigger a side effect

🟡 **L3218** [技术债务]: (anijain2305) - Investigate if we need specialization for more

🟡 **L3394** [技术债务]: - Check what is this _is_c_defined_property and if this handling should be moved inside the PropertyVariable.

🟡 **L3450** [技术债务]: - Check when are these called - and if we need to create new VTs.

🟡 **L3534** [技术债务]: (tp_descr_get) - Investigate if we need a separate descriptor

🟡 **L4390** [技术债务]: (follow-up): add test for unhashable/invalid key type, Counter missing key

🟡 **L4484** [技术债务]: move to dicts.py alongside ConstDictVariable and DefaultDictVariable.

🟡 **L4660** [技术债务]: move to dicts.py alongside ConstDictVariable.

🟡 **L5076** [技术债务]: this duplicates the logic in `BuiltinVariable(tuple)`


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/nn_module.py

🟡 **L535** [技术债务]: Use named_children when it supports remove_duplicate=False.

🟡 **L590** [技术债务]: do we want to support __call__ for GM's?

🟡 **L658** [技术债务]: (anijain2305,export-team) - Remove this if condition when inlining of inbuilt nn modules is

🟡 **L1244** [技术债务]: (anijain2305) - This might not be needed if we let Dynamo


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/builder.py

🟡 **L644** [技术债务]: storing a SymInt here but not a FakeTensor is a pretty strange

🟡 **L932** [技术债务]: (jansel): something like a REPR_MATCH might be more robust here

🟡 **L1292** [技术债务]: support source for sets and remove the special logics here.

🟡 **L1559** [技术债务]: this doing it manually is bad

🟡 **L1652** [技术债务]: (yidi): we need to figure out a way to propagate the guards

🟡 **L1840** [技术债务]: (jansel): combine this case with the one above

🟡 **L2858** [技术债务]: (pearu,sparse-team) - Add the corresponding SPARSE_TENSOR_MATCH guards

🟡 **L3129** [技术债务]: - Why do we need to set the source of the np ndarray vt back to

🟡 **L3178** [技术债务]: This should be dynamic, as we in general do not

🟡 **L3209** [技术债务]: dynamic_dim = DimDynamic.STATIC should work but

🟡 **L3239** [技术债务]: Do I actually need guard for constant source?

🟡 **L3333** [技术债务]: Switch RandomValueSource over to use this, this is more

🟡 **L3350** [技术债务]: Maybe the tensor-ification should be built into the source,

🟡 **L3472** [技术债务]: when can this happen?

🟡 **L3992** [技术债务]: this is a little sus, because we didn't check what the self is

🟡 **L4103** [技术债务]: not sure about this fake mode test

🟡 **L4658** [技术债务]: index export_constraints ahead of time so we don't have to

🟡 **L4737** [技术债务]: This can be batched

🟡 **L4738** [技术债务]: Doing this here is kind of sus, maybe better to set this

🟡 **L4844** [技术债务]: When does this show up?

🟡 **L5008** [技术债务]: for TensorGuards, this eventually may need more

🟡 **L5013** [技术债务]: revise this, but for now this stride instead of ()


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/tensor.py

🟡 **L618** [技术债务]: - This is not a good solution but solves an accuracy issue.

🟡 **L2019** [技术债务]: (jansel): returning None here is wrong, it should be

🟡 **L2546** [技术债务]: Should we allow non SymTypes here?  Today it is allowed

🟡 **L3235** [技术债务]: builder should be able to handle `torch.Tensor.__init__`,


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/higher_order_ops.py

🟡 **L631** [技术债务]: floats are not supported in HOP input/output

🟡 **L1097** [技术债务]: - write an example with tensor as a graph attribute in

🟡 **L1101** [技术债务]: - call_module is not supported because Dynamo Fx graph does

🟡 **L1609** [技术债务]: - The eventual goal is to replace

🟡 **L1681** [技术债务]: - supports input_mutation and aliasing should be False by default for strictness

🟡 **L1885** [技术债务]: - Today this is supported only for AC. AC HOP gets

🟡 **L2015** [技术债务]: - supports input_mutation and aliasing should be False by default for strictness

🟡 **L2105** [技术债务]: - clean up num_intermediate_nodes_as_outputs - we do not need

🟡 **L2110** [技术债务]: support pytree output

🟡 **L2391** [技术债务]: (voz): Support fake tensor dispatch for recursive

🟡 **L2483** [技术债务]: Support kwargs

🟡 **L2496** [技术债务]: - removing consts from control flow ops need more work

🟡 **L3270** [技术债务]: Support kwargs

🟡 **L3287** [技术债务]: - removing consts from control flow ops need more work

🟡 **L3939** [技术债务]: (tmanlaibaatar) support pytree here

🟡 **L4913** [技术债务]: - revisit if we need the python dispatcher

🟡 **L5092** [技术债务]: - revisit if we need enable_grad

🟡 **L5100** [技术债务]: - Do not support this path because of eager

🟡 **L5941** [技术债务]: Figure out how to handle output order diverging from eager


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/builtin.py

🟡 **L633** [技术债务]: If we expand this to handle tensor args, we need to manually

🟡 **L3252** [技术债务]: (mlazos) - Do we need this?

🟡 **L3378** [技术债务]: (azahed98): Make it work properly

🟡 **L3389** [技术债务]: (azahed98): The plan of record is to introduce a set_data op, entirely subsume the


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/lazy.py

🟡 **L267** [技术债务]: Add support for more types


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/torch.py

🟡 **L1935** [技术债务]: this probably should be folded somewhere else but I'm not sure where

🟡 **L1936** [技术债务]: some of the other symbolic_shapes special tools can also get this treatment too

🟡 **L1953** [技术债务]: this probably should be folded somewhere else but I'm not sure where

🟡 **L1954** [技术债务]: some of the other symbolic_shapes special tools can also get this treatment too

🟡 **L1969** [技术债务]: this probably should be folded somewhere else but I'm not sure where

🟡 **L1970** [技术债务]: some of the other symbolic_shapes special tools can also get this treatment too

🟡 **L2144** [技术债务]: there maybe other recursive structures you need to

🟡 **L3165** [技术债务]: (voz): Replace w/ dynamic shape rewrite table.

🟡 **L3176** [技术债务]: for each of the following check on `out=` or `requires_grad=`

🟡 **L3891** [技术债务]: (jansel/bdhirsh) - There is some issue with

🟡 **L3902** [技术债务]: (jansel): if the new param falls out of scope, currently it won't get freed until


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/dicts.py

🟡 **L948** [技术债务]: (follow-up): add tests for invalid key type, missing key


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/base.py

🟡 **L513** [技术债务]: when LazyConstants are fully landed, we can use them here instead.

🟡 **L668** [技术债务]: raise TypeError instead - Make sure the jit tests for ScriptDict/ScriptList works with


### venv/lib/python3.13/site-packages/torch/_dynamo/repro/after_dynamo.py

🟡 **L199** [技术债务]: Figure out why torch.compile'd hash isn't work on this codepath

🟡 **L299** [技术债务]: factor this out

🟡 **L328** [技术债务]: It's inconsistent to pass SymInt inputs but REAL tensors.

🟡 **L508** [技术债务]: disable clone


### venv/lib/python3.13/site-packages/torch/_dynamo/repro/after_aot.py

🟡 **L307** [技术债务]: why do we need to deepcopy the original graph?

🟡 **L319** [技术债务]: Failures here are troublesome because no real inputs,

🟡 **L715** [技术债务]: we may need to solve expressions to extract symbol definitions.

🟡 **L900** [技术债务]: factor this out

🟡 **L1177** [技术债务]: speed this up

🟡 **L1287** [技术债务]: The logic for cloning inputs/models here is intentionally

🟡 **L1385** [技术债务]: check eager determinism

🟡 **L1470** [技术债务]: lazily load the inputs or something, rather than cloning them

🟡 **L1621** [技术债务]: make this an option for --analyze too


### venv/lib/python3.13/site-packages/torch/_dynamo/polyfills/__init__.py

🟡 **L527** [技术债务]: Enabling the `elif`-branch below needs too many `VariableClass.call_obj_hasattr` changes.


### venv/lib/python3.13/site-packages/torch/ao/ns/_numeric_suite_fx.py

🟡 **L220** [技术债务]: (future PR): consider designing this better, as the difference

🟡 **L226** [技术债务]: (future PR): consider refactoring this to better reuse the parent

🟡 **L253** [技术债务]: (future PR): make the comparison function configurable

🟡 **L408** [技术债务]: (future PR): expose these

🟡 **L447** [技术债务]: (future PR): do not observe nodes we do not care

🟡 **L549** [技术债务]: (future PR): expose these

🟡 **L587** [技术债务]: (future PR): better check when scripted

🟡 **L630** [技术债务]: (future PR): align on naming

🟡 **L724** [技术债务]: (future PR): expose these

🟡 **L917** [技术债务]: (future PR): deduplicate repeating entries

🟡 **L949** [技术债务]: (future PR): we should rethink the names of all the PNP APIs

🟡 **L1030** [技术债务]: (future PR): we should rethink the names of all the PNP APIs

🟡 **L1056** [技术债务]: (future PR): consider aligning API signature with other similar quantization

🟡 **L1067** [技术债务]: (future PR): consider aligning API signature with other similar quantization

🟡 **L1091** [技术债务]: (future PR): consider matching in a safer way than


### venv/lib/python3.13/site-packages/torch/ao/quantization/observer.py

🟡 **L367** [技术债务]: (jakeszwe, jerryzh168)

🟡 **L415** [技术债务]: switch to scale.item() after adding JIT support

🟡 **L418** [技术债务]: switch to zero_point.item() after adding JIT support

🟡 **L436** [技术债务]: (after v1.13): delete this

🟡 **L524** [技术债务]: MinMaxObserver by itself doesn't support dynamic quantization, but

🟡 **L1317** [技术债务]: For some reason, this is required for it to pass torchscript test

🟡 **L2138** [技术债务]: (future PR): remove these defaults and enforce activation functions

🟡 **L2146** [技术债务]: the following 2 variables are kept for backwards compatibility; remove after a few releases


### venv/lib/python3.13/site-packages/torch/ao/quantization/quantization_mappings.py

🟡 **L180** [技术债务]: merge with default static mapping

🟡 **L345** [技术债务]: merge with get_static_quant_module_class


### venv/lib/python3.13/site-packages/torch/ao/quantization/quantize.py

🟡 **L55** [技术债务]: remove this once BC is no longer required to avoid a SEV

🟡 **L241** [技术债务]: remove Dropout special after codebase stable

🟡 **L277** [技术债务]: These are the modules that cannot be observed

🟡 **L387** [技术债务]: remove allow_list

🟡 **L412** [技术债务]: maybe we should change activation_post_process to _activation_post_process

🟡 **L436** [技术债务]: rename to something more general


### venv/lib/python3.13/site-packages/torch/ao/quantization/fake_quantize.py

🟡 **L198** [技术债务]: keeping self.quant_min/max for BC; remove after a couple releases

🟡 **L339** [技术债务]: rename observer to observer_ctr

🟡 **L484** [技术债务]: the following 2 variables are kept for backwards compatibility; remove after a few releases


### venv/lib/python3.13/site-packages/torch/ao/quantization/qconfig.py

🟡 **L285** [技术债务]: make this compatible with xnnpack constraints

🟡 **L448** [技术债务]: make this compatible with xnnpack constraints


### venv/lib/python3.13/site-packages/torch/ao/quantization/qconfig_mapping.py

🟡 **L40** [技术债务]: replace all usages with these constants

🟡 **L47** [技术债务]: derive this map from the BackendConfig

🟡 **L124** [技术债务]: Currently it's required that separate ops in a fused op/module have the same qconfig.

🟡 **L139** [技术债务]: add assert for backend choices

🟡 **L323** [技术债务]: remove this

🟡 **L350** [技术债务]: remove this


### venv/lib/python3.13/site-packages/torch/ao/quantization/utils.py

🟡 **L34** [技术债务]: not sure if typing supports recursive data types

🟡 **L46** [技术债务]: maybe rename this to MatchInputNode

🟡 **L129** [技术债务]: not used now, remove

🟡 **L455** [技术债务]: (jerryzh): Figure out why custom quant_min/quant_max are still adjusted.

🟡 **L706** [技术债务]: switch to scale.item() after adding JIT support

🟡 **L709** [技术债务]: switch to zero_point.item() after adding JIT support


### venv/lib/python3.13/site-packages/torch/ao/quantization/quant_type.py

🟡 **L26** [技术债务]: make this private


### venv/lib/python3.13/site-packages/torch/ao/quantization/quantize_fx.py

🟡 **L354** [技术债务]: add backend_config after we split the backend_config for fbgemm and qnnpack

🟡 **L493** [技术债务]: add backend_config after we split the backend_config for fbgemm and qnnpack

🟡 **L619** [技术债务]: add backend_config after we split the backend_config for fbgemm and qnnpack

🟡 **L670** [技术债务]: add backend_config after we split the backend_config for fbgemm and qnnpack

🟡 **L722** [技术债务]: add backend_config after we split the backend_config for fbgemm and qnnpack


### venv/lib/python3.13/site-packages/torch/ao/nn/quantized/modules/activation.py

🟡 **L255** [技术债务]: This is a potential source of accuracy drop.


### venv/lib/python3.13/site-packages/torch/ao/nn/quantized/modules/conv.py

🟡 **L157** [技术债务]: maybe change to this when https://github.com/pytorch/pytorch/pull/32958 is landed


### venv/lib/python3.13/site-packages/torch/ao/nn/quantized/dynamic/modules/rnn.py

🟡 **L318** [技术债务]: dedup with __init__ of RNNBase

🟡 **L1155** [技术债务]: these can be simplified to one level? e.g. using weight_ih as key

🟡 **L1170** [技术债务]: these can be simplified to one level? e.g. using weight_ih as key

🟡 **L1266** [技术债务]: remove when jit supports exception flow


### venv/lib/python3.13/site-packages/torch/ao/nn/quantized/reference/modules/utils.py

🟡 **L209** [技术债务]: add an util function for converting qdtype to dtype

🟡 **L235** [技术债务]: torch.quint4x2 is not supported

🟡 **L265** [技术债务]: get the quant_min and quant_max from activation_post_process

🟡 **L271** [技术债务]: add an util function for converting qdtype to dtype

🟡 **L295** [技术债务]: torch.quint4x2 is not supported


### venv/lib/python3.13/site-packages/torch/ao/nn/quantized/reference/modules/rnn.py

🟡 **L72** [技术债务]: (jerryzh168): maybe make this arg a required arg

🟡 **L99** [技术债务]: refactor the duplicated code to utils.py

🟡 **L186** [技术债务]: refactor nn.RNNCell to have a _forward that takes weight_ih and weight_hh as input

🟡 **L223** [技术债务]: remove when jit supports exception flow

🟡 **L426** [技术债务]: (jerryzh168): maybe make this arg a required arg

🟡 **L748** [技术债务]: maybe we can try inheriting from that class and define get_flat_weights


### venv/lib/python3.13/site-packages/torch/ao/nn/quantizable/modules/activation.py

🟡 **L379** [技术债务]: This method has some duplicate lines with the


### venv/lib/python3.13/site-packages/torch/ao/nn/quantizable/modules/rnn.py

🟡 **L140** [技术债务]: make this tanh a member of the module so its qparams can be configured


### venv/lib/python3.13/site-packages/torch/ao/nn/intrinsic/quantized/modules/bn_relu.py

🟡 **L53** [技术债务]: Add qat support for BNReLU2d

🟡 **L105** [技术债务]: Add qat support for BNReLU3d


### venv/lib/python3.13/site-packages/torch/ao/nn/intrinsic/quantized/modules/conv_relu.py

🟡 **L20** [技术债务]: factor out the common parts to ConvNd


### venv/lib/python3.13/site-packages/torch/ao/nn/intrinsic/quantized/dynamic/modules/linear_relu.py

🟡 **L47** [技术债务]: check if we should set reduce_rage = True by default here


### venv/lib/python3.13/site-packages/torch/ao/nn/sparse/quantized/linear.py

🟡 **L13** [技术债务]: (zaf): Inherit from `quantized.LinearPackedParams` (T83294430)

🟡 **L105** [技术债务]: (zaf): Inherit from `quantized.Linear` (T83294430)

🟡 **L256** [技术债务]: Need to add options to qconfig to avoid the calibration.

🟡 **L257** [技术债务]: Add calibration for the sparsity


### venv/lib/python3.13/site-packages/torch/ao/nn/sparse/quantized/dynamic/linear.py

🟡 **L154** [技术债务]: Need to add options to qconfig to avoid the calibration.

🟡 **L155** [技术债务]: Add calibration for the sparsity

🟡 **L173** [技术债务]: (zaf): Mask might not be part of the qconfig (T83295194)


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/graph_passes.py

🟡 **L284** [技术债务]: (future PR): determine the actual dtype of node_c,

🟡 **L368** [技术债务]: (future PR): add handling for quantize_per_tensor

🟡 **L395** [技术债务]: (future PR): look into using copy_node API instead

🟡 **L561** [技术债务]: (future PR): enable multiple inputs for nodes which are not at start of subgraph

🟡 **L991** [技术债务]: explain this


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/weight_utils.py

🟡 **L70** [技术债务]: (future PR): make more generic, handle everything

🟡 **L173** [技术债务]: (future PR): why does packed_weight.unpack() not work?


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/graph_matcher.py

🟡 **L197** [技术债务]: (next): make this code handle matching by what is before the base op

🟡 **L225** [技术债务]: (future PR): check for matches start_op_node and base_op_node


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/utils.py

🟡 **L23** [技术债务]: (future PR): consider deleting this enum and using the torch types

🟡 **L30** [技术债务]: (future PR): while these functions can support multiple dtypes,

🟡 **L35** [技术债务]: (future PRs): dynamic quant, fake quant, etc

🟡 **L44** [技术债务]: (future PR): clean this up

🟡 **L212** [技术债务]: (future PR): handle more functionals

🟡 **L213** [技术债务]: (future PR): handle functional ops which inherit qparams from input

🟡 **L340** [技术债务]: (future PR): use relationship map instead of hardcoding


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/pattern_utils.py

🟡 **L23** [技术债务]: (future PR): allow customizations

🟡 **L24** [技术债务]: (future PR): reuse existing quantization mappings

🟡 **L25** [技术债务]: (future PR): add the rest of modules and ops here

🟡 **L71** [技术债务]: (future PR): allow customizations from default patterns.

🟡 **L76** [技术债务]: this is a temporary hack to flatten the patterns from quantization so


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/ns_types.py

🟡 **L20** [技术债务]: (future PR): see if we can use typing_extensions's TypedDict instead


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/n_shadows_utils.py

🟡 **L12** [技术债务]: (future PR): make this work correctly for methods

🟡 **L27** [技术债务]: (future PR): reuse existing mapping instead of creating a new one

🟡 **L114** [技术债务]: (future PR): try reversed(list(matches.items()))

🟡 **L172** [技术债务]: (future PR): make this code less confusing,  see discussion

🟡 **L251** [技术债务]: (future PR): reconsider the design to make this more intuitive.

🟡 **L315** [技术债务]: (future): some graphs could have placeholders which are unrelated

🟡 **L356** [技术债务]: (future PR): handle non-normalized kwargs

🟡 **L391** [技术债务]: (future PR): this is not handling complicated graphs correctly, need to

🟡 **L393** [技术债务]: (future PR): this is ignoring kwargs, will need to support kwargs

🟡 **L484** [技术债务]: (future PR): move logger classes to utils to remove circular dependency

🟡 **L523** [技术债务]: (future PR): deduplicate equivalent qconfigs that come from

🟡 **L570** [技术债务]: (future PR): handle fusion patterns where non-first nodes

🟡 **L593** [技术债务]: (future PR): clarify why we are adding kwargs to args

🟡 **L662** [技术债务]: (future PR): add a test case for this once we have an easy

🟡 **L677** [技术债务]: (future): consider making this configurable

🟡 **L764** [技术债务]: (future PR): move logger classes to utils to remove circular dependency

🟡 **L882** [技术债务]: (future PR): make this support all possible args/kwargs

🟡 **L897** [技术债务]: (future PR): set name explicitly

🟡 **L1089** [技术债务]: (future PR): move this to config

🟡 **L1101** [技术债务]: (future PR, if needed): support kwargs

🟡 **L1102** [技术债务]: (future PR, if needed): support multiple shadow users

🟡 **L1179** [技术债务]: (future PR): redesign this to make it easier to consume outputs

🟡 **L1272** [技术债务]: (future PR): redesign this to make it easier to consume outputs

🟡 **L1352** [技术债务]: (future PR): redesign this to make it easier to consume outputs


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/mappings.py

🟡 **L490** [技术债务]: (future PR): clean this up


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/_common_operator_config_utils.py

🟡 **L32** [技术债务]: rename to be more explicit, e.g. qat_conv_relu

🟡 **L139** [技术债务]: this is not used right now since we have extra check in prepare

🟡 **L410** [技术债务]: we can add fusion for torch.relu as well


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/qnnpack.py

🟡 **L82** [技术债务]: add additional restriction on qscheme to ensure it


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/fbgemm.py

🟡 **L27** [技术债务]: For now, these DTypeConfigs are identical to the ones defined in native.py


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/native.py

🟡 **L173** [技术债务]: express this BackendConfig as a union of the FBGEMM and QNNPACK BackendConfigs


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/utils.py

🟡 **L191** [技术债务]: (future PR): move backend_config_dict to use dataclass and move this logic to


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/_qnnpack_pt2e.py

🟡 **L94** [技术债务]: remove when functionalization is supported in PT2 mode

🟡 **L144** [技术债务]: this is not used right now since we have extra check in prepare

🟡 **L158** [技术债务]: remove when functionalization is supported in pt2_mode


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/executorch.py

🟡 **L1** [技术债务]: rename executorch to qnnpack_executorch since executorch is a general runtime

🟡 **L261** [技术债务]: we can add fusion for torch.relu as well

🟡 **L305** [技术债务]: this is not used right now since we have extra check in prepare


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/backend_config.py

🟡 **L53** [技术债务]: maybe rename this to something that's not related to observer


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/convert.py

🟡 **L163** [技术债务]: probably should cleanup this condition check, it's hard

🟡 **L210** [技术债务]: we can add the information of whether a value needs to

🟡 **L222** [技术债务]: maybe need more complex attr name here

🟡 **L318** [技术债务]: we can add the information of whether a value needs to

🟡 **L425** [技术债务]: probably should cleanup this condition check, it's hard

🟡 **L455** [技术债务]: we can add the information of whether a value needs to

🟡 **L459** [技术债务]: maybe need more complex attr name here

🟡 **L483** [技术债务]: get reduce range from observer

🟡 **L508** [技术债务]: we can add the information of whether a value needs to

🟡 **L525** [技术债务]: DeQuantStubs are currently inserted only after custom module LSTM, while observers are inserted

🟡 **L663** [技术债务]: it's not used, so actually we can skip quantization

🟡 **L714** [技术债务]: remove is_reference flag

🟡 **L749** [技术债务]: allow convert_custom_config to override backend_config

🟡 **L810** [技术债务]: rename weight_is_statically_quantized to weight_is_int8_quantized

🟡 **L825** [技术债务]: move this to the reference quantized module

🟡 **L989** [技术债务]: This is the first step in enabling the full fx custom module

🟡 **L1134** [技术债务]: refactor this code once we update the prepare logic to have additional information on

🟡 **L1310** [技术债务]: maybe move this to quantize_fx.py

🟡 **L1316** [技术债务]: this looks hacky, we want to check why we need this and see if we can


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/quantize_handler.py

🟡 **L164** [技术债务]: remove this class, this is still exposed in torch.ao.quantization

🟡 **L174** [技术债务]: remove this class

🟡 **L179** [技术债务]: remove this class

🟡 **L184** [技术债务]: remove this class

🟡 **L189** [技术债务]: remove this class

🟡 **L194** [技术债务]: remove this class

🟡 **L199** [技术债务]: remove this class

🟡 **L204** [技术债务]: remove this class

🟡 **L209** [技术债务]: remove

🟡 **L214** [技术债务]: remove


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/utils.py

🟡 **L43** [技术债务]: revisit this list. Many helper methods shouldn't be public

🟡 **L249** [技术债务]: delete

🟡 **L334** [技术债务]: (future PR): remove this entire function  and

🟡 **L354** [技术债务]: (future PR): remove this entire function  and

🟡 **L885** [技术债务]: log warnings only when the user enabled a debug flag

🟡 **L894** [技术债务]: for now, just use the existing eps value as scale_min. In the future, we should

🟡 **L940** [技术债务]: handle fp16 qconfigs properly


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/_lower_to_native_backend.py

🟡 **L268** [技术债务]: correct the namespace for these modules

🟡 **L274** [技术债务]: merge with STATIC_LOWER_MODULE_MAP after we merge

🟡 **L303** [技术债务]: LinearLeakyReLU is registered as global but it is only fused and

🟡 **L399** [技术债务]: add tests for lowering these ops

🟡 **L877** [技术债务]: maybe define a WeightedDynamicallyQuantizedModule

🟡 **L901** [技术债务]: WeightedQuantizedModule is currently assuming static quant apis

🟡 **L904** [技术债务]: maybe define a WeightedWeightOnlyQuantizedModule

🟡 **L1238** [技术债务]: add safety checks that users for the ref_node and dq_node needs to be one

🟡 **L1243** [技术债务]: add a warning or error out here? (bc-breaking if error out)

🟡 **L1253** [技术债务]: add a warning or error out here? (bc-breaking if error out)

🟡 **L1288** [技术债务]: enable we have patterns that needs to swap the modules


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/custom_config.py

🟡 **L24** [技术债务]: replace all usages with these constants

🟡 **L183** [技术债务]: remove this

🟡 **L418** [技术债务]: remove this

🟡 **L497** [技术债务]: remove this


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/fuse.py

🟡 **L27** [技术债务]: We should make this private in the future

🟡 **L78** [技术债务]: change this to inplace changes to graph, since we no longer construct

🟡 **L119** [技术债务]: add validation that root_node is a module and has the same type

🟡 **L153** [技术债务]: dedup with quantization matching function in match_utils.py


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/qconfig_mapping_utils.py

🟡 **L75** [技术债务]: currently it only works for modules,

🟡 **L77** [技术债务]: currently it only works for object_type configurations,


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/match_utils.py

🟡 **L18** [技术债务]: (future PR): the 1st argument is typed as `List[Node]`, but a better type


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/prepare.py

🟡 **L168** [技术债务]: instead of instantiating the instance, we can use inspect to get the default args

🟡 **L198** [技术债务]: support check for standalone module

🟡 **L212** [技术债务]: (future PR): remove the cast to bool below after figuring

🟡 **L222** [技术债务]: move dtype check into `_qconfig_satisfies_dtype_config_constraints` as well

🟡 **L237** [技术债务]: move dtype check into `_qconfig_satisfies_dtype_config_constraints` as well

🟡 **L258** [技术债务]: move dtype check into `_qconfig_satisfies_dtype_config_constraints` as well

🟡 **L260** [技术债务]: we should check is_dynamic here as well, the code from _is_input_arg_dtype_supported_by_backend

🟡 **L272** [技术债务]: this is a hack because we can only specify one activation_obs_or_fq for

🟡 **L475** [技术债务]: refactor the following code in terms of apply a qconfig to a pattern

🟡 **L765** [技术债务]: move this to a separate function

🟡 **L778** [技术债务]: we are assuming "target_dtype_info" exists here, maybe

🟡 **L853** [技术债务]: this is looking into how the value is used in the future

🟡 **L1141** [技术债务]: this does not handle dynamic quantization yet

🟡 **L1216** [技术债务]: probably need to remove `is_general_tensor_value_op`

🟡 **L1363** [技术债务]: (future PR): delete the orphaned observer modules

🟡 **L1476** [技术债务]: we probably don't need this counter since each graph will only have

🟡 **L1541** [技术债务]: (future PR): update the output_quantized_idxs API to match

🟡 **L1546** [技术债务]: (future PR): support more dtypes in model outputs, if necessary

🟡 **L1581** [技术债务]: we might want to handle these more uniformly with the default path

🟡 **L1618** [技术债务]: reuse placeholder_node_to_input_index and output_node_to_output_index

🟡 **L1626** [技术债务]: change this to insert obs/fq by pattern instead of by node

🟡 **L1659** [技术债务]: take a closer look to see if we can remove this check

🟡 **L1763** [技术债务]: This currently diverges from how custom modules are handled today,

🟡 **L2072** [技术债务]: support regex as well


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/_decomposed.py

🟡 **L172** [技术债务]: remove other variants and keep this one

🟡 **L286** [技术债务]: investigate why

🟡 **L386** [技术债务]: remove other variants and keep this one

🟡 **L1032** [技术债务]: support fp16

🟡 **L1042** [技术债务]: dtype is ignored for now

🟡 **L1066** [技术债务]: check for dtype, currently we can't express torch.int4 so it's omitted


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/fuse_handler.py

🟡 **L109** [技术债务]: change the signature for fuser_method to take matched module patterns

🟡 **L127** [技术债务]: is this logic right?


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/lstm_utils.py

🟡 **L22** [技术债务]: move all LSTM util functions from fx/utils.py to this file

🟡 **L109** [技术债务]: maybe make this work for layer_bw as well


### venv/lib/python3.13/site-packages/torch/ao/pruning/sparsifier/base_sparsifier.py

🟡 **L28** [技术债务]: update desc with new config args

🟡 **L166** [技术债务]: Need to figure out how to load without this.

🟡 **L173** [技术债务]: Remove the configuration by reference ('module')

🟡 **L303** [技术债务]: handle multiple tensor being quantized on a single module, where to store sparse_params?


### venv/lib/python3.13/site-packages/torch/ao/pruning/_experimental/pruner/base_structured_sparsifier.py

🟡 **L110** [技术债务]: LSTM Structured pruning does not support returned state currently.


### venv/lib/python3.13/site-packages/torch/_refs/special/__init__.py

🟡 **L235** [技术债务]: add docstring


### venv/lib/python3.13/site-packages/torch/_refs/nn/functional/__init__.py

🟡 **L608** [技术债务]: Raise exception instead of converting value.  This is only for

🟡 **L633** [技术债务]: Raise exception instead of converting value.  This is only for

🟡 **L697** [技术债务]: Raise exception instead of converting value.  This is only for

🟡 **L745** [技术债务]: Enable data-dependent checks with debug mode

🟡 **L746** [技术债务]: This check does not work with FakeTensor inputs; See Issue #85834

🟡 **L825** [技术债务]: raise exception instead of converting value

🟡 **L881** [技术债务]: This ref supports int reduction and out kwarg to be compatible with ATen:

🟡 **L883** [技术债务]: Could be rewritten to support complex:

🟡 **L967** [技术债务]: Raise exception instead of converting value.  This is only for

🟡 **L1150** [技术债务]: Raise exception instead of converting value.  This is only for


### venv/lib/python3.13/site-packages/torch/export/experimental/__init__.py

🟡 **L416** [技术债务]: also dump kwargs

🟡 **L417** [技术债务]: currently only support list of Tensors and they need to be on the same device


### venv/lib/python3.13/site-packages/torch/export/experimental/_utils.py

🟡 **L86** [技术债务]: add device


### venv/lib/python3.13/site-packages/torch/export/pt2_archive/_package.py

🟡 **L700** [技术债务]: turn this into an error

🟡 **L1120** [技术债务]: turn this into an error in 2.9


### venv/lib/python3.13/site-packages/torch/nested/_internal/nested_tensor.py

🟡 **L205** [技术债务]: Revisit this when @properties are better supported by PT2. I think the ideal

🟡 **L293** [技术债务]: Remove this in favor of the default tensor subclass serialization logic.

🟡 **L464** [技术债务]: Remove ViewBufferFromNested, ViewNestedFromBuffer, and buffer_from_jagged once the

🟡 **L584** [技术债务]: An alternative way to construct offsets is to use F.pad. This avoids creating


### venv/lib/python3.13/site-packages/torch/nested/_internal/ops.py

🟡 **L600** [技术债务]: write a kernel for this

🟡 **L603** [技术债务]: We probably want the output to have the same ragged structure / nested int.

🟡 **L730** [技术债务]: eventually do a direct copy when this is possible

🟡 **L1306** [技术债务]: Back these with proper kernels (e.g. grouped GEMM)

🟡 **L1773** [技术债务]: Do this for all other views!

🟡 **L1908** [技术债务]: make this more efficient

🟡 **L2359** [技术债务]: Handle inference mode properly.

🟡 **L2391** [技术债务]: Handle the rest of output_size


### venv/lib/python3.13/site-packages/torch/nested/_internal/sdpa.py

🟡 **L67** [技术债务]: Figure out whether masks are actually supported for this layout or not

🟡 **L352** [技术债务]: Explore performance impact of copying

🟡 **L357** [技术债务]: Explore performance impact of copying

🟡 **L362** [技术债务]: Explore performance impact when compiling

🟡 **L407** [技术债务]: Next iteration should add test cases and check it works

🟡 **L641** [技术债务]: coalesce with torch/nn/utils/attention.py

🟡 **L643** [技术债务]: Investigate why math.sqrt() isn't properly handled by Dynamo?


### venv/lib/python3.13/site-packages/mpl_toolkits/mplot3d/axes3d.py

🟡 **L2099** [技术债务]: Operate on each axes separately

🟡 **L2646** [技术债务]: Support masked arrays

🟡 **L2783** [技术债务]: Support custom face colours

🟡 **L3131** [技术债务]: arbitrary default

🟡 **L3133** [技术债务]: use issubclass() (although, then a 3D collection


### venv/lib/python3.13/site-packages/mpl_toolkits/mplot3d/axis3d.py

🟡 **L383** [技术债务]: Move somewhere else where it's triggered less:

🟡 **L612** [技术债务]: Maybe Text objects should handle this themselves?

🟡 **L686** [技术债务]: Get this to work (more) properly when mplot3d supports the


### venv/lib/python3.13/site-packages/mpl_toolkits/mplot3d/art3d.py

🟡 **L1506** [技术债务]: Some results still don't look quite right.


### venv/lib/python3.13/site-packages/mpl_toolkits/axisartist/axis_artist.py

🟡 **L70** [技术债务]: :


### venv/lib/python3.13/site-packages/mpl_toolkits/axisartist/floating_axes.py

🟡 **L5** [技术债务]: :


### venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py

🟡 **L2136** [技术债务]: this is not working for params like ":param case_sensitive=True:"

🟡 **L2166** [技术债务]: this still won't cover if the code example itself has


### venv/lib/python3.13/site-packages/sqlalchemy/ext/compiler.py

🟡 **L535** [技术债务]: why is the lambda needed ?

🟡 **L570** [技术债务]: yes, this could also switch off of DBAPI in use.


### venv/lib/python3.13/site-packages/sqlalchemy/ext/baked.py

🟡 **L528** [技术债务]: can mapper._get_clause be pre-adapted?


### venv/lib/python3.13/site-packages/sqlalchemy/ext/horizontal_shard.py

🟡 **L456** [技术债务]: if we had an ORMOption that gets applied at ORM statement


### venv/lib/python3.13/site-packages/sqlalchemy/ext/associationproxy.py

🟡 **L1628** [技术债务]: no idea how to do this without separate "stub"

🟡 **L1721** [技术债务]: again, no idea how to create an actual MutableMapping.


### venv/lib/python3.13/site-packages/sqlalchemy/testing/pickleable.py

🟡 **L41** [技术债务]: these are kind of arbitrary....


### venv/lib/python3.13/site-packages/sqlalchemy/testing/engines.py

🟡 **L270** [技术债务]: this doesn't cover all cases


### venv/lib/python3.13/site-packages/sqlalchemy/testing/util.py

🟡 **L224** [技术债务]: this warning can be used to find all the places

🟡 **L330** [技术债务]: :


### venv/lib/python3.13/site-packages/sqlalchemy/testing/assertsql.py

🟡 **L276** [技术债务]: why do we need this part?


### venv/lib/python3.13/site-packages/sqlalchemy/testing/requirements.py

🟡 **L146** [技术债务]: exclusions should be composable,


### venv/lib/python3.13/site-packages/sqlalchemy/orm/interfaces.py

🟡 **L142** [技术债务]: add python_type and sql_type here; combining them


### venv/lib/python3.13/site-packages/sqlalchemy/orm/decl_base.py

🟡 **L1527** [技术债务]: should "registry" here be also?   might be too late


### venv/lib/python3.13/site-packages/sqlalchemy/orm/instrumentation.py

🟡 **L715** [技术债务]: we should use the ClassManager's notion of the

🟡 **L725** [技术债务]: need to juggle local names to avoid constructor argument


### venv/lib/python3.13/site-packages/sqlalchemy/orm/loading.py

🟡 **L470** [技术债务]: no coverage here

🟡 **L1262** [技术债务]: polymorphic_from seems to be a Mapper in all cases.

🟡 **L1281** [技术债务]: we are currently ignoring the case where the

🟡 **L1373** [技术债务]: allow "existing" populator to know this is

🟡 **L1382** [技术债务]: same path


### venv/lib/python3.13/site-packages/sqlalchemy/orm/persistence.py

🟡 **L461** [技术债务]: ordered values, etc

🟡 **L890** [技术债务]: why with bookkeeping=False?

🟡 **L1490** [技术债务]: why does this "only warn" if versioning is turned off,

🟡 **L1727** [技术债务]: this still goes a little too often.  would be nice to


### venv/lib/python3.13/site-packages/sqlalchemy/orm/path_registry.py

🟡 **L220** [技术债务]: what are we using this for?


### venv/lib/python3.13/site-packages/sqlalchemy/orm/query.py

🟡 **L1292** [技术债务]: deprecate, property has to be supplied

🟡 **L1335** [技术债务]: deprecate

🟡 **L2840** [技术债务]: not sure why we can't use result.scalar() here

🟡 **L2994** [技术债务]: isn't this supposed to be a list?


### venv/lib/python3.13/site-packages/sqlalchemy/orm/attributes.py

🟡 **L598** [技术债务]: can move this to descriptor_props if the need for this

🟡 **L1104** [技术债务]: no test coverage here.

🟡 **L1913** [技术债务]: better solution here would be to add

🟡 **L2305** [技术债务]: need coverage in test/orm/ of remove event

🟡 **L2621** [技术债务]: this appears to be the WriteOnlyAttributeImpl /


### venv/lib/python3.13/site-packages/sqlalchemy/orm/strategies.py

🟡 **L243** [技术债务]: check all columns ?  check for foreign key as well?

🟡 **L743** [技术债务]: the "not self.uselist" can be taken out entirely; a m2o


### venv/lib/python3.13/site-packages/sqlalchemy/orm/strategy_options.py

🟡 **L1435** [技术债务]: no cases in test suite where we actually get

🟡 **L2373** [技术债务]: need to figure out this None thing being returned by

🟡 **L2444** [技术债务]: attrs against different classes.  we likely have to


### venv/lib/python3.13/site-packages/sqlalchemy/orm/events.py

🟡 **L1081** [技术债务]: need coverage for this event

🟡 **L2521** [技术债务]: coverage


### venv/lib/python3.13/site-packages/sqlalchemy/orm/mapper.py

🟡 **L1989** [技术债务]: what happens if polymorphic_on column attribute name

🟡 **L4431** [技术债务]: weakref would be a good idea here


### venv/lib/python3.13/site-packages/sqlalchemy/orm/session.py

🟡 **L1200** [技术债务]: shouldn't we only be here if not

🟡 **L1429** [技术债务]: these two None sets were historically after the

🟡 **L3862** [技术债务]: this was being tested before, but this is not possible


### venv/lib/python3.13/site-packages/sqlalchemy/orm/context.py

🟡 **L431** [技术债务]: this structure is set up by JoinedLoader

🟡 **L1294** [技术债务]: some complexity with order_by here was due to mapper.order_by.

🟡 **L1398** [技术债务]: this goes away once we get rid of the deep entity

🟡 **L2195** [技术债务]: should we be checking for multiple mapper entities

🟡 **L2272** [技术债务]: we had orm_only=False here before, removing

🟡 **L3259** [技术债务]: polymorphic subclasses ?


### venv/lib/python3.13/site-packages/sqlalchemy/orm/dependency.py

🟡 **L251** [技术债务]: add a high speed method

🟡 **L393** [技术债务]: this whole block is not covered

🟡 **L1037** [技术债务]: no tests fail if this whole


### venv/lib/python3.13/site-packages/sqlalchemy/orm/descriptor_props.py

🟡 **L646** [技术债务]: need a deserialize hook here

🟡 **L988** [技术债务]: when initialized, check _proxied_object,


### venv/lib/python3.13/site-packages/sqlalchemy/orm/bulk_persistence.py

🟡 **L896** [技术债务]: dive more into how a local table PK is used for fetch

🟡 **L2122** [技术债务]: inline this and call remove_newly_deleted


### venv/lib/python3.13/site-packages/sqlalchemy/orm/unitofwork.py

🟡 **L280** [技术债务]: store the history as (state, object) tuples


### venv/lib/python3.13/site-packages/sqlalchemy/orm/relationships.py

🟡 **L2528** [技术债务]: coverage


### venv/lib/python3.13/site-packages/sqlalchemy/engine/events.py

🟡 **L566** [技术债务]: deprecate "context"

🟡 **L578** [技术债务]: deprecate "context"


### venv/lib/python3.13/site-packages/sqlalchemy/engine/result.py

🟡 **L324** [技术债务]: are we freezing the result with or without uniqueness

🟡 **L2389** [技术债务]: this throws away the iterator which may be holding


### venv/lib/python3.13/site-packages/sqlalchemy/engine/cursor.py

🟡 **L281** [技术债务]: need unit test for:

🟡 **L869** [技术债务]: can consider pre-loading ints and negative ints

🟡 **L917** [技术债务]: consider serializing this as SimpleResultMetaData

🟡 **L1989** [技术债务]: if these are Row objects, can we save on not having to


### venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py

🟡 **L1504** [技术债务]: should this be _return_conn?


### venv/lib/python3.13/site-packages/sqlalchemy/sql/functions.py

🟡 **L424** [技术债务]: this might not be fully accurate


### venv/lib/python3.13/site-packages/sqlalchemy/sql/_selectable_constructors.py

🟡 **L107** [技术债务]: mypy requires the _TypedSelectable overloads in all compound select


### venv/lib/python3.13/site-packages/sqlalchemy/sql/compiler.py

🟡 **L3147** [技术债务]: would need a fast cast again here,

🟡 **L3792** [技术债务]: this condition is not well understood.

🟡 **L3984** [技术债务]: accumulate_bind_names is passed by crud.py to gather

🟡 **L4192** [技术债务]: can we get at the .columns_plus_names collection

🟡 **L4196** [技术债务]: proxy_name is not technically safe,

🟡 **L4601** [技术债务]: this only seems to be tested indirectly

🟡 **L5420** [技术债务]: likely need asfrom=True here?

🟡 **L5508** [技术债务]: do we want non-primary key explicit sentinel cols

🟡 **L6550** [技术债务]: remove in 2.1

🟡 **L7674** [技术债务]: no coverage here


### venv/lib/python3.13/site-packages/sqlalchemy/sql/traversals.py

🟡 **L358** [技术债务]: use abc classes

🟡 **L833** [技术债务]: look at attrname for "legacy_join" and use different structure


### venv/lib/python3.13/site-packages/sqlalchemy/sql/cache_key.py

🟡 **L176** [技术债务]: wouldn't we instead get this from our superclass?

🟡 **L276** [技术债务]: see if C code can help here as Python lacks an


### venv/lib/python3.13/site-packages/sqlalchemy/sql/roles.py

🟡 **L283** [技术债务]: are we using this?


### venv/lib/python3.13/site-packages/sqlalchemy/sql/util.py

🟡 **L929** [技术债务]: add specific coverage here

🟡 **L936** [技术债务]: add specific coverage here

🟡 **L1147** [技术债务]: cython candidate

🟡 **L1448** [技术债务]: typing is finding a few gaps in here, see if they can be


### venv/lib/python3.13/site-packages/sqlalchemy/sql/elements.py

🟡 **L755** [技术债务]: this code is uncovered and in all likelihood is not included

🟡 **L2100** [技术债务]: set up protocol for bind parameter callable

🟡 **L2610** [技术债务]: this seems wrong, it seems like we might not

🟡 **L4755** [技术债务]: this is only covered in test_text.py, but nothing

🟡 **L4766** [技术债务]: no coverage for this block, again would be in


### venv/lib/python3.13/site-packages/sqlalchemy/sql/selectable.py

🟡 **L4495** [技术债务]: this is hacky and slow

🟡 **L6914** [技术债务]: this seems like we should be using coercions for this


### venv/lib/python3.13/site-packages/sqlalchemy/sql/coercions.py

🟡 **L758** [技术债务]: there's no test coverage now for the

🟡 **L1256** [技术债务]: doing _implicit_subquery here causes tests to fail,


### venv/lib/python3.13/site-packages/sqlalchemy/sql/base.py

🟡 **L333** [技术债务]: cython candidate

🟡 **L935** [技术债务]: very inefficient.  This is used only in test suites

🟡 **L943** [技术债务]: fairly inefficient, used only in debugging right now.

🟡 **L1950** [技术债务]: cython candidate


### venv/lib/python3.13/site-packages/sqlalchemy/sql/crud.py

🟡 **L700** [技术债务]: - see TODO(return_defaults_columns) below

🟡 **L728** [技术债务]: - see TODO(return_defaults_columns) below

🟡 **L823** [技术债务]: (return_defaults_columns): there can still be more columns in

🟡 **L1452** [技术债务]: no test coverage for literal binds here

🟡 **L1585** [技术债务]: not sure if accumulated_bind_names applies here

🟡 **L1712** [技术债务]: this is weird.  See #9685 where we have to


### venv/lib/python3.13/site-packages/sqlalchemy/sql/lambdas.py

🟡 **L378** [技术债务]: this needs A LOT of tests

🟡 **L479** [技术债务]: TEST TEST TEST, this is very out there

🟡 **L494** [技术债务]: A LOT A LOT of tests.   for _resolve_with_args, we don't know

🟡 **L740** [技术债务]: validate kw haven't changed?

🟡 **L897** [技术债务]: should we coerce consts None/True/False here?

🟡 **L1321** [技术债务]: coverage where an ORM option or similar is here

🟡 **L1411** [技术债务]: coverage


### venv/lib/python3.13/site-packages/sqlalchemy/sql/schema.py

🟡 **L2489** [技术债务]: likely should be copied in all cases

🟡 **L2490** [技术债务]: if a Sequence, we would need to transfer the Sequence

🟡 **L2499** [技术债务]: DefaultGenerator is not copied here!  it's just used again

🟡 **L3271** [技术债务]: no test coverage for self not in memos

🟡 **L5276** [技术债务]: consider "table" argument being public, but for


### venv/lib/python3.13/site-packages/sqlalchemy/ext/mypy/util.py

🟡 **L290** [技术债务]: figure out a more robust way to check this.  The node is some


### venv/lib/python3.13/site-packages/sqlalchemy/ext/mypy/infer.py

🟡 **L181** [技术债务]: handle mypy.types.Overloaded

🟡 **L301** [技术债务]: look at generic ref and either use that,

🟡 **L571** [技术债务]: support other pep-435 types here


### venv/lib/python3.13/site-packages/sqlalchemy/ext/mypy/decl_class.py

🟡 **L135** [技术债务]: this is nearly the same logic as that of

🟡 **L429** [技术债务]: do we need to convert from unbound for this case?


### venv/lib/python3.13/site-packages/sqlalchemy/testing/suite/test_results.py

🟡 **L257** [技术债务]: this is a huge issue as it prevents these tests from being

🟡 **L334** [技术债务]: need a real requirement for this, or dont use this test


### venv/lib/python3.13/site-packages/sqlalchemy/testing/suite/test_reflection.py

🟡 **L61** [技术债务]: when temp tables are subject to server reset,


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py

🟡 **L682** [技术债务]: looks like we have to hand-roll some kind of batching here.


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/postgresql/base.py

🟡 **L2279** [技术债务]: this coercion should be up front.  we can't cache

🟡 **L3530** [技术债务]: ugly hack to get out of transaction


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/oracle/provision.py

🟡 **L221** [技术债务]: oracledb claims to have this feature built in somehow,


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/oracle/cx_oracle.py

🟡 **L660** [技术债务]: the names used across CHAR / VARCHAR / NCHAR / NVARCHAR

🟡 **L804** [技术债务]: we could likely do away with quoting altogether for

🟡 **L1482** [技术债务]: Others ?

🟡 **L1491** [技术债务]: others?

🟡 **L1517** [技术债务]: need to end XA state here

🟡 **L1532** [技术债务]: need to end XA state here


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/oracle/dictionary.py

🟡 **L445** [技术债务]: figure out if it's still relevant, since there is no mention from here


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/sqlite/aiosqlite.py

🟡 **L122** [技术债务]: base on connectors/asyncio.py

🟡 **L227** [技术债务]: base on connectors/asyncio.py


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/sqlite/provision.py

🟡 **L28** [技术债务]: I can't get this to build dynamically with pytest-xdist procs


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/sqlite/base.py

🟡 **L2057** [技术债务]: detect SQLite version 3.10.0 or greater;


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mysql/enumerated.py

🟡 **L118** [技术债务]: SET is a string as far as configuration but does not act like


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mysql/types.py

🟡 **L120** [技术债务]: float arguments?


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mysql/base.py

🟡 **L1500** [技术债务]: this coercion should be up front.  we can't cache

🟡 **L1822** [技术债务]: remove ??


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mssql/pymssql.py

🟡 **L70** [技术债务]: monkeypatching here is less than ideal


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mssql/information_schema.py

🟡 **L176** [技术债务]: is CATLOG misspelled ?


### venv/lib/python3.13/site-packages/sqlalchemy/dialects/mssql/base.py

🟡 **L2134** [技术债务]: Why?  shouldn't we use TOP always ?

🟡 **L2511** [技术债务]: does this comment (from mysql) apply to here, too?

🟡 **L3416** [技术债务]: try to avoid having to run a separate query here

🟡 **L4063** [技术债务]: we support match=<keyword> for foreign keys so


### venv/lib/python3.13/site-packages/numpy/ma/core.py

🟡 **L229** [技术债务]: This is probably a mess, but should best preserve behavior?

🟡 **L472** [技术债务]: It seems better to always store a valid fill_value, the oddity

🟡 **L2911** [技术债务]: should we set `_data._sharedmask = True`?

🟡 **L4779** [技术债务]: We don't actually support K, so use A instead.  We could


### venv/lib/python3.13/site-packages/numpy/_core/_dtype.py

🟡 **L176** [技术债务]: this path can never be reached

🟡 **L185** [技术债务]: this duplicates the C metastr_to_unicode functionality


### venv/lib/python3.13/site-packages/numpy/_core/_add_newdocs_scalars.py

🟡 **L128** [技术债务]: These docs probably need an if to highlight the default rather than

🟡 **L337** [技术债务]: work out how to put this on the base class, np.floating


### venv/lib/python3.13/site-packages/numpy/_core/numeric.py

🟡 **L511** [技术债务]: this works around .astype(bool) not working properly (gh-9847)


### venv/lib/python3.13/site-packages/numpy/_core/arrayprint.py

🟡 **L1548** [技术债务]: Custom repr for user DTypes, logic should likely move.


### venv/lib/python3.13/site-packages/numpy/_typing/_char_codes.py

🟡 **L212** [技术债务]: add `_StringCodes` once it has a scalar type


### venv/lib/python3.13/site-packages/numpy/_typing/_dtype_like.py

🟡 **L62** [技术债务]: wait for support for recursive types


### venv/lib/python3.13/site-packages/numpy/_typing/_array_like.py

🟡 **L65** [技术债务]: Wait until mypy supports recursive objects in combination with typevars


### venv/lib/python3.13/site-packages/numpy/f2py/cfuncs.py

🟡 **L846** [技术债务]: These should be dynamically generated, too many mapped to int things,


### venv/lib/python3.13/site-packages/numpy/f2py/crackfortran.py

🟡 **L2484** [技术债务]: test .eq., .neq., etc replacements.

🟡 **L2573** [技术债务]: use symbolic from PR #19805


### venv/lib/python3.13/site-packages/numpy/f2py/f2py2e.py

🟡 **L458** [技术债务]: Remove all this when scaninputline is replaced

🟡 **L650** [技术债务]: Once distutils is dropped completely, i.e. min_ver >= 3.12, unify into --fflags


### venv/lib/python3.13/site-packages/numpy/f2py/symbolic.py

🟡 **L23** [技术债务]: support logical constants (Op.BOOLEAN)

🟡 **L24** [技术债务]: support logical operators (.AND., ...)

🟡 **L25** [技术债务]: support defined operators (.MYOP., ...)

🟡 **L520** [技术债务]: other kind not used

🟡 **L811** [技术债务]: determine correct kind

🟡 **L846** [技术债务]: determine correct kind

🟡 **L896** [技术债务]: denom kind not used

🟡 **L1108** [技术债务]: find common divisor of coefficients


### venv/lib/python3.13/site-packages/numpy/f2py/capi_maps.py

🟡 **L248** [技术债务]: support Fortran `len` function with optional kind parameter

🟡 **L504** [技术债务]: Evaluate intent_flags here.


### venv/lib/python3.13/site-packages/numpy/f2py/_isocbind.py

🟡 **L55** [技术债务]: See gh-25229


### venv/lib/python3.13/site-packages/numpy/lib/mixins.py

🟡 **L168** [技术债务]: handle the optional third argument for __pow__?


### venv/lib/python3.13/site-packages/numpy/lib/recfunctions.py

🟡 **L1557** [技术债务]: nb2 below is never used. Commenting out for pyflakes.


### venv/lib/python3.13/site-packages/numpy/lib/_npyio_impl.py

🟡 **L234** [技术债务]: This seems like it will copy strings around

🟡 **L2252** [技术债务]: possible error as following variable never used.


### venv/lib/python3.13/site-packages/numpy/lib/_function_base_impl.py

🟡 **L848** [技术债务]: This preserves the Python int, float, complex manually to get the


### venv/lib/python3.13/site-packages/numpy/lib/_nanfunctions_impl.py

🟡 **L1693** [技术债务]: What to do when arr1d = [1, np.nan] and weights = [0, 1]?


### venv/lib/python3.13/site-packages/numpy/lib/_datasource.py

🟡 **L72** [技术债务]: .zip support, .tar support?

🟡 **L331** [技术债务]: Doesn't handle compressed files!

🟡 **L397** [技术债务]: This should be more robust.  Handles case where path includes

🟡 **L511** [技术债务]: There is no support for opening a file for writing which

🟡 **L514** [技术债务]: Add a ``subdir`` parameter for specifying the subdirectory


### venv/lib/python3.13/site-packages/numpy/polynomial/_polybase.py

🟡 **L433** [技术债务]: we're stuck with disabling math formatting until we handle


### venv/lib/python3.13/site-packages/numpy/polynomial/polyutils.py

🟡 **L536** [技术债务]: add message with details to exception


### venv/lib/python3.13/site-packages/numpy/polynomial/chebyshev.py

🟡 **L798** [技术债务]: add message with details to exception


### venv/lib/python3.13/site-packages/numpy/polynomial/polynomial.py

🟡 **L405** [技术债务]: add message with details to exception


### venv/lib/python3.13/site-packages/numpy/linalg/tests/test_linalg.py

🟡 **L1036** [技术债务]: the 'e' dtype might work in future


### venv/lib/python3.13/site-packages/numpy/ma/tests/test_core.py

🟡 **L5522** [技术债务]: Test masked_object, masked_equal, ...


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_scalarmath.py

🟡 **L96** [技术债务]: It would be nice to resolve this issue.

🟡 **L1132** [技术债务]: Power is a bit special, but here mostly bools seem to behave oddly


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_array_coercion.py

🟡 **L455** [技术债务]: This discrepancy _should_ be resolved, either by relaxing the

🟡 **L905** [技术债务]: This is arguably weird/wrong, but seems old:


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_machar.py

🟡 **L19** [技术债务]: , this needs to raise a 'skip' exception.


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_umath.py

🟡 **L1138** [技术债务]: cinf not tested.

🟡 **L1865** [技术债务]: NAN raises FP invalid exception:

🟡 **L2923** [技术债务]: a not used


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_datetime.py

🟡 **L1579** [技术债务]: Allowing unsafe casting by

🟡 **L2561** [技术债务]: add absolute (gold standard) time span limit strings


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_umath_complex.py

🟡 **L12** [技术债务]: branch cuts (use Pauli code)

🟡 **L13** [技术债务]: conj 'symmetry'

🟡 **L14** [技术债务]: FPU exceptions

🟡 **L19** [技术债务]: this will probably change when we require full C99 compatibility

🟡 **L23** [技术债务]: replace with a check on whether platform-provided C99 funcs are used

🟡 **L26** [技术债务]: This can be xfail when the generator functions are got rid of.

🟡 **L122** [技术债务]: This can be xfail when the generator functions are got rid of.

🟡 **L337** [技术债务]: ugly workaround for isinf bug.

🟡 **L479** [技术债务]: This can be xfail when the generator functions are got rid of.


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_casting_unittests.py

🟡 **L781** [技术债务]: While this test is fairly thorough, right now, it does not


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_stringdtype.py

🟡 **L1577** [技术债务]: generalize to more ufuncs


### venv/lib/python3.13/site-packages/numpy/_core/tests/test_multiarray.py

🟡 **L6296** [技术债务]: :

🟡 **L7584** [技术债务]: test for multidimensional


### venv/lib/python3.13/site-packages/numpy/typing/tests/data/pass/shape.py

🟡 **L11** [技术债务]: remove this cast after: https://github.com/numpy/numpy/pull/27171


### venv/lib/python3.13/site-packages/numpy/f2py/tests/test_f2py2e.py

🟡 **L415** [技术债务]: Clean up to prevent passing --overwrite-signature

🟡 **L682** [技术债务]: populate

🟡 **L691** [技术债务]: populate

🟡 **L747** [技术债务]: f2py2e should not call sys.exit() after printing the version

🟡 **L821** [技术债务]: These should be tested separately

🟡 **L827** [技术债务]: populate

🟡 **L835** [技术债务]: populate

🟡 **L843** [技术债务]: populate

🟡 **L851** [技术债务]: populate

🟡 **L859** [技术债务]: populate

🟡 **L867** [技术债务]: populate

🟡 **L875** [技术债务]: populate

🟡 **L883** [技术债务]: populate

🟡 **L891** [技术债务]: populate

🟡 **L899** [技术债务]: populate

🟡 **L907** [技术债务]: populate

🟡 **L915** [技术债务]: populate

🟡 **L923** [技术债务]: populate

🟡 **L931** [技术债务]: populate

🟡 **L939** [技术债务]: populate

🟡 **L947** [技术债务]: populate

🟡 **L955** [技术债务]: populate

🟡 **L963** [技术债务]: populate


### venv/lib/python3.13/site-packages/numpy/lib/tests/test_type_check.py

🟡 **L271** [技术债务]: , wrong place, isfinite now ufunc

🟡 **L302** [技术债务]: , wrong place, isinf now ufunc


### venv/lib/python3.13/site-packages/numpy/lib/tests/test_io.py

🟡 **L313** [技术债务]: specify exact message


### venv/lib/python3.13/site-packages/numpy/lib/tests/test_function_base.py

🟡 **L4437** [技术债务]: Median does not support Datetime, due to `mean`.


### venv/lib/python3.13/site-packages/numpy/random/tests/test_random.py

🟡 **L1063** [技术债务]: Include test for randint once it can broadcast


### venv/lib/python3.13/site-packages/pandas_ta/trend/cksp.py

🟡 **L54** [技术债务]: clean up x and q


### venv/lib/python3.13/site-packages/pandas_ta/utils/_numba.py

🟡 **L96** [技术债务]: Handle negative rolling windows


### venv/lib/python3.13/site-packages/osqp/nn/torch.py

🟡 **L134** [技术债务]: Cache solver object in between

🟡 **L144** [技术债务]: Deep copy when available

🟡 **L160** [技术债务]: We can replace this with something calmer and

🟡 **L181** [技术债务]: (Bart): create CSC matrix during initialization. Then


### venv/lib/python3.13/site-packages/html5lib/treeadapters/genshi.py

🟡 **L51** [技术债务]: What to do?


### venv/lib/python3.13/site-packages/pip/_internal/cache.py

🟡 **L283** [技术债务]: use DirectUrl.equivalent when


### venv/lib/python3.13/site-packages/pip/_internal/build_env/venv.py

🟡 **L142** [技术债务]: when better support for installing to arbitrary Python environments


### venv/lib/python3.13/site-packages/pip/_internal/build_env/installer.py

🟡 **L169** [技术债务]: this plays poorly with venv-based build environments, but cannot be

🟡 **L205** [技术债务]: hash-checking should be extended to build deps, but that is


### venv/lib/python3.13/site-packages/pip/_internal/build_env/base.py

🟡 **L92** [技术债务]: Consider direct URL?


### venv/lib/python3.13/site-packages/pip/_internal/network/lazy_wheel.py

🟡 **L179** [技术债务]: Get range requests to be correctly cached


### venv/lib/python3.13/site-packages/pip/_internal/utils/compat.py

🟡 **L37** [技术债务]: Remove the 3.10 fallback once pip drops Python 3.10 support.


### venv/lib/python3.13/site-packages/pip/_internal/utils/pylock.py

🟡 **L252** [技术债务]: refactor - this is similar to req_file.get_file_content

🟡 **L293** [技术债务]: for completeness, pylock.select should support preferring sdist


### venv/lib/python3.13/site-packages/pip/_internal/models/installation_report.py

🟡 **L51** [技术债务]: currently, the resolver uses the default environment to evaluate


### venv/lib/python3.13/site-packages/pip/_internal/cli/base_command.py

🟡 **L226** [技术债务]: Try to get these passing down from the command?


### venv/lib/python3.13/site-packages/pip/_internal/cli/main.py

🟡 **L78** [技术债务]: Re-evaluate whether this is still needed once pip drops Python 3.10.


### venv/lib/python3.13/site-packages/pip/_internal/operations/prepare.py

🟡 **L689** [技术债务]: separate this part out from RequirementPreparer when the v1

🟡 **L763** [技术债务]: https://github.com/pypa/pip/issues/11943

🟡 **L801** [技术债务]: this is a hack for checking whether a distribution is metadata-


### venv/lib/python3.13/site-packages/pip/_internal/req/req_install.py

🟡 **L349** [技术债务]: Is there a better place to create the build_dir? (hg and bzr


### venv/lib/python3.13/site-packages/pip/_internal/req/req_uninstall.py

🟡 **L488** [技术债务]: need a test for this elif block


### venv/lib/python3.13/site-packages/pip/_internal/req/req_file.py

🟡 **L248** [技术债务]: it would be nice to keep track of the source


### venv/lib/python3.13/site-packages/pip/_internal/req/constructors.py

🟡 **L313** [技术债务]: The is_installable_dir test here might not be necessary

🟡 **L594** [技术债务]: validate file size


### venv/lib/python3.13/site-packages/pip/_internal/vcs/subversion.py

🟡 **L60** [技术债务]: should we warn?


### venv/lib/python3.13/site-packages/pip/_internal/locations/base.py

🟡 **L16** [技术债务]: doesn't account for venv linked to global site-packages

🟡 **L60** [技术债务]: keep src in cwd for now (it is not a temporary folder)


### venv/lib/python3.13/site-packages/pip/_internal/index/collector.py

🟡 **L345** [技术债务]: In the future, it would be nice if pip supported PEP 691


### venv/lib/python3.13/site-packages/pip/_internal/commands/inspect.py

🟡 **L60** [技术债务]: tags? scheme?


### venv/lib/python3.13/site-packages/pip/_internal/metadata/base.py

🟡 **L177** [技术债务]: get project location from second line of egg_link file


### venv/lib/python3.13/site-packages/pip/_internal/resolution/resolvelib/factory.py

🟡 **L195** [技术债务]: Check already installed candidate, and use it if the link and

🟡 **L638** [技术债务]: Are there more cases this needs to return True? Editable?


### venv/lib/python3.13/site-packages/pip/_internal/resolution/resolvelib/candidates.py

🟡 **L236** [技术债务]: performance: this means we iterate the dependencies at least twice,

🟡 **L381** [技术债务]: Supply reason based on force_reinstall and upgrade_strategy.


### venv/lib/python3.13/site-packages/pip/_vendor/packaging/tags.py

🟡 **L559** [技术债务]: Need to care about 32-bit PPC for ppc64 through 10.2?


### venv/lib/python3.13/site-packages/pip/_vendor/packaging/metadata.py

🟡 **L205** [技术债务]: The spec doesn't say anything about if the keys should be

🟡 **L869** [技术债务]: 2.1: can be in body


### venv/lib/python3.13/site-packages/pip/_vendor/packaging/version.py

🟡 **L423** [技术债务]: remove "no cover" when Python 3.9 is dropped.


### venv/lib/python3.13/site-packages/pip/_vendor/packaging/requirements.py

🟡 **L48** [技术债务]: Can we test whether something is contained within a requirement?

🟡 **L51** [技术债务]: Can we normalize the name and extra name?


### venv/lib/python3.13/site-packages/pip/_vendor/truststore/_macos.py

🟡 **L558** [技术债务]: Not sure if we need the SecTrustResultType for anything?


### venv/lib/python3.13/site-packages/pip/_vendor/msgpack/fallback.py

🟡 **L499** [技术债务]: should we eliminate the recursion?

🟡 **L503** [技术债务]: check whether we need to call `list_hook`

🟡 **L511** [技术债务]: is the interaction between `list_hook` and `use_list` ok?

🟡 **L516** [技术债务]: check whether we need to call hooks


### venv/lib/python3.13/site-packages/pip/_vendor/distlib/util.py

🟡 **L401** [技术债务]: check k, v for valid values


### venv/lib/python3.13/site-packages/pip/_vendor/cachecontrol/controller.py

🟡 **L227** [技术债务]: There is an assumption that the result will be a


### venv/lib/python3.13/site-packages/pip/_vendor/cachecontrol/filewrapper.py

🟡 **L68** [技术债务]: Add some logging here...


### venv/lib/python3.13/site-packages/pip/_vendor/requests/_types.py

🟡 **L55** [技术债务]: move to collections.abc when Python >= 3.12

🟡 **L56** [技术债务]: move to typing when Python >= 3.13


### venv/lib/python3.13/site-packages/pip/_vendor/requests/hooks.py

🟡 **L29** [技术债务]: response is the only one


### venv/lib/python3.13/site-packages/pip/_vendor/requests/models.py

🟡 **L1012** [技术债务]: remove cast after iter_lines rewrite


### venv/lib/python3.13/site-packages/pip/_vendor/requests/adapters.py

🟡 **L715** [技术债务]: Remove this in 3.0.0: see #2811


### venv/lib/python3.13/site-packages/pip/_vendor/rich/text.py

🟡 **L562** [技术债务]: This is a little inefficient, it is only used by full justify


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/_base_connection.py

🟡 **L22** [技术债务]: Remove this in favor of a better


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/response.py

🟡 **L902** [技术债务]: Ideally we'd like to include the url in the ReadTimeoutError but

🟡 **L1146** [技术债务]: make sure to initially read enough data to get past the headers

🟡 **L1211** [技术债务]: , this method's type doesn't say returning None is possible

🟡 **L1389** [技术债务]: Rewrite this method and make it a class with a better structured logic.


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/exceptions.py

🟡 **L306** [技术债务]: (t-8ch): Stop inheriting from AssertionError in v2.0.


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/connectionpool.py

🟡 **L578** [技术债务]: Add optional support for socket.gethostbyname checking.

🟡 **L1108** [技术债务]: revise this, see https://github.com/urllib3/urllib3/issues/2791


### venv/lib/python3.13/site-packages/pip/_vendor/pkg_resources/__init__.py

🟡 **L1** [技术债务]: Add Generic type annotations to initialized collections.

🟡 **L122** [技术债务]: / Incomplete: A readable file-like object

🟡 **L2031** [技术债务]: 'ZipProvider._extract_resource' is too complex (12)

🟡 **L3201** [技术债务]: 'Distribution.insert_on' is too complex (13)

🟡 **L3598** [技术债务]: Add a deadline?


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/util/response.py

🟡 **L99** [技术债务]: Can we do this somehow without accessing private httplib _method?


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/util/url.py

🟡 **L454** [技术债务]: Remove this when we break backwards compatibility.


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/http2/__init__.py

🟡 **L38** [技术债务]: Offer 'http/1.1' as well, but for testing purposes this is handy.


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/http2/connection.py

🟡 **L144** [技术债务]: SKIPPABLE_HEADERS from urllib3 are ignored.

🟡 **L234** [技术债务]: Arbitrary read value.

🟡 **L282** [技术债务]: this is often present from upstream.

🟡 **L325** [技术债务]: This is a woefully incomplete response object, but works for non-streaming.

🟡 **L332** [技术债务]: support decoding


### venv/lib/python3.13/site-packages/sklearn/tree/_classes.py

🟡 **L441** [技术债务]: tree shouldn't need this in this case

🟡 **L619** [技术债务]: the tree shouldn't need this param

🟡 **L1349** [技术债务]: (1.11): remove support of "friedman_mse" criterion.


### venv/lib/python3.13/site-packages/sklearn/metrics/_scorer.py

🟡 **L185** [技术债务]: (slep006): remove when metadata routing is the only way

🟡 **L264** [技术债务]: (slep006): remove when metadata routing is the only way

🟡 **L280** [技术债务]: (1.11): remove decorator and sample_weight param from signature

🟡 **L540** [技术债务]: (slep006): remove when metadata routing is the only way


### venv/lib/python3.13/site-packages/sklearn/metrics/_classification.py

🟡 **L3416** [技术债务]: (1.11): Remove check and remove default value for `y_proba`.

🟡 **L3933** [技术债务]: (1.11): Remove check and remove default value for `y_proba`.


### venv/lib/python3.13/site-packages/sklearn/metrics/pairwise.py

🟡 **L2001** [技术债务]: do it also for other norms.


### venv/lib/python3.13/site-packages/sklearn/ensemble/_base.py

🟡 **L29** [技术债务]: (SLEP6): remove if-condition for unrouted sample_weight when metadata


### venv/lib/python3.13/site-packages/sklearn/ensemble/_forest.py

🟡 **L499** [技术债务]: we could consider to support multiclass-multioutput if

🟡 **L1940** [技术债务]: (1.11): remove support of "friedman_mse" criterion.

🟡 **L2692** [技术债务]: (1.11): remove support of "friedman_mse" criterion.


### venv/lib/python3.13/site-packages/sklearn/ensemble/_gb.py

🟡 **L116** [技术债务]: Use loss.fit_intercept_only where appropriate instead of

🟡 **L265** [技术债务]: Multiply here by learning rate instead of everywhere else.

🟡 **L460** [技术债务]: Without oob, i.e. with self.subsample = 1.0, we could call

🟡 **L691** [技术债务]: Is this still required?


### venv/lib/python3.13/site-packages/sklearn/ensemble/_stacking.py

🟡 **L745** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.

🟡 **L1129** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.


### venv/lib/python3.13/site-packages/sklearn/cluster/_agglomerative.py

🟡 **L609** [技术债务]: We compute all the distances, while we could have only computed


### venv/lib/python3.13/site-packages/sklearn/cluster/_optics.py

🟡 **L621** [技术债务]: handle working_memory somehow?


### venv/lib/python3.13/site-packages/sklearn/feature_extraction/text.py

🟡 **L1744** [技术债务]: np.float16 could be preserved if _inplace_csr_row_normalize_l2


### venv/lib/python3.13/site-packages/sklearn/_loss/link.py

🟡 **L153** [技术债务]: Should we copy?


### venv/lib/python3.13/site-packages/sklearn/_loss/loss.py

🟡 **L1646** [技术债务]: once incremental assignment for multiple integer array


### venv/lib/python3.13/site-packages/sklearn/compose/_target.py

🟡 **L282** [技术债务]: a FunctionTransformer can return a 1D array even when validate


### venv/lib/python3.13/site-packages/sklearn/datasets/_svmlight_format_io.py

🟡 **L557** [技术债务]: We can do this cheaper; sorted_indices copies the whole matrix.


### venv/lib/python3.13/site-packages/sklearn/datasets/_openml.py

🟡 **L345** [技术债务]: feature request OpenML.


### venv/lib/python3.13/site-packages/sklearn/tests/test_metaestimators.py

🟡 **L279** [技术债务]: remove data validation for the following estimators


### venv/lib/python3.13/site-packages/sklearn/tests/test_multioutput.py

🟡 **L748** [技术债务]: we should move this test in `estimator_checks` once we are able


### venv/lib/python3.13/site-packages/sklearn/tests/test_docstring_parameters.py

🟡 **L187** [技术债务]: (1.10): remove copy warning filter

🟡 **L219** [技术债务]: (devtools): use _tested_estimators instead of all_estimators in the

🟡 **L239** [技术债务]: (1.10) remove

🟡 **L243** [技术债务]: (1.10) remove l1_ratios

🟡 **L244** [技术债务]: (1.11) remove completely


### venv/lib/python3.13/site-packages/sklearn/tests/test_multiclass.py

🟡 **L916** [技术债务]: we should move this test in `estimator_checks` once we are able


### venv/lib/python3.13/site-packages/sklearn/tests/test_min_dependencies_readme.py

🟡 **L157** [技术债务]: remove this when our minimum supported numpy version is >=2.


### venv/lib/python3.13/site-packages/sklearn/tests/test_metadata_routing.py

🟡 **L951** [技术债务]: these test classes can be moved to sklearn.utils._testing once we


### venv/lib/python3.13/site-packages/sklearn/tests/test_calibration.py

🟡 **L1306** [技术债务]: Also ensure that `CalibratedClassifierCV` works appropriately with


### venv/lib/python3.13/site-packages/sklearn/tests/test_metaestimators_metadata_routing.py

🟡 **L140** [技术债务]: (1.11): remove scoring because neg_log_loss is default now


### venv/lib/python3.13/site-packages/sklearn/tests/test_naive_bayes.py

🟡 **L74** [技术债务]: Remove this test once the more general partial_fit tests are merged

🟡 **L322** [技术债务]: write a test to show this.


### venv/lib/python3.13/site-packages/sklearn/tests/test_pipeline.py

🟡 **L1826** [技术债务]: Replace this test with a full `check_estimator` once we have API only


### venv/lib/python3.13/site-packages/sklearn/linear_model/_base.py

🟡 **L52** [技术债务]: bayesian_ridge_regression and bayesian_regression_ard

🟡 **L891** [技术债务]: instead of warning and recomputing, we could just center


### venv/lib/python3.13/site-packages/sklearn/linear_model/_least_angle.py

🟡 **L817** [技术债务]: better names for these variables: z

🟡 **L874** [技术债务]: this could be updated

🟡 **L892** [技术债务]: this could be updated


### venv/lib/python3.13/site-packages/sklearn/linear_model/_passive_aggressive.py

🟡 **L16** [技术债务]: (1.10): Remove

🟡 **L342** [技术债务]: (1.10): Remove


### venv/lib/python3.13/site-packages/sklearn/linear_model/_logistic.py

🟡 **L96** [技术债务]: (1.10): update message to remove "as well as penalty=None".

🟡 **L176** [技术债务]: (1.10): use the return value of ``call_on_fit_task_end`` (a bool

🟡 **L560** [技术债务]: (callbacks) When adding callback support to LogisticRegressionCV,

🟡 **L1332** [技术债务]: (callbacks): update/remove as more solvers get supported.

🟡 **L1541** [技术债务]: enable multi-threading if benchmarks show a positive effect,

🟡 **L2480** [技术债务]: (1.11): remove this decorator along with `sample_weight` from the `score`

🟡 **L2511** [技术债务]: (1.11): for backwards compatibility, when `sample_weight` becomes a part

🟡 **L2577** [技术债务]: (1.11): remove


### venv/lib/python3.13/site-packages/sklearn/linear_model/_omp.py

🟡 **L1072** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.


### venv/lib/python3.13/site-packages/sklearn/linear_model/_linear_loss.py

🟡 **L22** [技术债务]: This "sandwich product" is the main computational bottleneck for solvers


### venv/lib/python3.13/site-packages/sklearn/linear_model/_coordinate_descent.py

🟡 **L165** [技术债务]: For y.ndim >> 1, think about avoiding memory of y = y - y.mean()

🟡 **L220** [技术债务]: (1.11): remove "warn" and None options.

🟡 **L396** [技术债务]: (1.11): remove n_alphas and alphas={"warn", None}; set alphas=100 by default.

🟡 **L457** [技术债务]: (1.11): remove "warn" and None options.

🟡 **L631** [技术债务]: (1.11): remove n_alphas and alphas={"warn", None}; set alphas=100 by default.

🟡 **L1775** [技术债务]: Sample_weights?


### venv/lib/python3.13/site-packages/sklearn/linear_model/_ridge.py

🟡 **L1628** [技术债务]: (1.11) raise ValueError


### venv/lib/python3.13/site-packages/sklearn/linear_model/_stochastic_gradient.py

🟡 **L159** [技术债务]: Consider whether pa1 and pa2 could also work for other losses.


### venv/lib/python3.13/site-packages/sklearn/impute/__init__.py

🟡 **L13** [技术债务]: remove this check once the estimator is no longer experimental.

🟡 **L19** [技术债务]: remove this check once the estimator is no longer experimental.


### venv/lib/python3.13/site-packages/sklearn/utils/optimize.py

🟡 **L37** [技术债务]: use the `line_search_wolfe1` from `scipy` when it is array API compliant.

🟡 **L155** [技术债务]: It seems that the new check for the sum of absolute gradients above


### venv/lib/python3.13/site-packages/sklearn/utils/fixes.py

🟡 **L34** [技术债务]: We can consider removing the containers and importing

🟡 **L57** [技术债务]: Remove when SciPy 1.11 is the minimum supported version

🟡 **L68** [技术债务]: Remove when Scipy 1.12 is the minimum supported version

🟡 **L73** [技术债务]: Remove when Scipy 1.15 is the minimum supported version

🟡 **L78** [技术债务]: Remove when Scipy 1.12 is the minimum supported version

🟡 **L199** [技术债务]: Adapt when Pandas > 2.2 is the minimum supported version

🟡 **L216** [技术债务]: remove when SciPy 1.12 is the minimum supported version

🟡 **L263** [技术债务]: remove when SciPy 1.12 is the minimum supported version

🟡 **L333** [技术债务]: Remove when SciPy 1.12 is the minimum supported version

🟡 **L342** [技术债务]: Remove when Python min version >= 3.12.

🟡 **L386** [技术债务]: Remove when Scipy 1.15 is the minimum supported version. In scipy 1.15,

🟡 **L396** [技术债务]: Replace when Scipy 1.12 is the minimum supported version

🟡 **L455** [技术债务]: remove when SciPy 1.15 is minimal supported version

🟡 **L472** [技术债务]: remove when SciPy 1.15 is minimal supported version

🟡 **L534** [技术债务]: remove when matplotlib 3.10 is the minimal supported version


### venv/lib/python3.13/site-packages/sklearn/utils/_array_api.py

🟡 **L25** [技术债务]: complete __all__

🟡 **L601** [技术债务]: try removing this once DLPack v1 more widely supported

🟡 **L602** [技术债务]: ValueError not needed once min NumPy >=2.4.0:

🟡 **L697** [技术债务]: when array libraries support `reshape(copy)`, use

🟡 **L727** [技术债务]: when array libraries support `reshape(copy)`, use

🟡 **L858** [技术债务]: consider simplifying this code to use scipy instead once the oldest

🟡 **L888** [技术债务]: refactor once nan-aware reductions are standardized:

🟡 **L908** [技术债务]: refactor once nan-aware reductions are standardized:

🟡 **L928** [技术债务]: refactor once nan-aware reductions are standardized:

🟡 **L943** [技术债务]: refactor once nan-aware reductions are standardized:

🟡 **L1202** [技术债务]: once sufficiently adopted, we might want to instead rely on the

🟡 **L1323** [技术债务]: update if bincount is ever adopted in a future version of the standard:

🟡 **L1339** [技术债务]: replace by scipy.special.logsumexp when


### venv/lib/python3.13/site-packages/sklearn/utils/estimator_checks.py

🟡 **L263** [技术债务]: test with intercept

🟡 **L264** [技术债务]: test with multiple responses

🟡 **L1194** [技术债务]: There are a few errors in SearchCV with array-api-strict because

🟡 **L3748** [技术债务]: find out why PLS and CCA fail. RANSAC is random

🟡 **L4086** [技术债务]: (devtools): this should be a separate check.

🟡 **L4117** [技术债务]: (devtools): separately check that the constructor doesn't


### venv/lib/python3.13/site-packages/sklearn/utils/_plotting.py

🟡 **L446** [技术债务]: (1.10): remove after the end of the deprecation period of `y_pred`


### venv/lib/python3.13/site-packages/sklearn/utils/_testing.py

🟡 **L1431** [技术债务]: remove when pyamg > 5.0.1

🟡 **L1512** [技术债务]: (1.10): remove PassiveAggressive


### venv/lib/python3.13/site-packages/sklearn/utils/extmath.py

🟡 **L1289** [技术债务]: (1.10): Remove


### venv/lib/python3.13/site-packages/sklearn/utils/parallel.py

🟡 **L155** [技术债务]: is there a simpler way that resetwarnings+ filterwarnings?


### venv/lib/python3.13/site-packages/sklearn/utils/_indexing.py

🟡 **L89** [技术债务]: `X_indexed` is a DataFrame with a single row; we return a Series to be

🟡 **L295** [技术债务]: we should probably use is_pandas_df_or_series(X) instead but:

🟡 **L349** [技术债务]: (1.3): check if the warning is still raised or remove the filter.


### venv/lib/python3.13/site-packages/sklearn/utils/validation.py

🟡 **L643** [技术债务]: Remove when the minimum version of SciPy supported is 1.12


### venv/lib/python3.13/site-packages/sklearn/covariance/_graph_lasso.py

🟡 **L147** [技术债务]: It is not ideal that the max_iter of the outer


### venv/lib/python3.13/site-packages/sklearn/neural_network/_base.py

🟡 **L211** [技术债务]: Decide what to do with the term `xlogy(y_true, y_true) - y_true`. For now,


### venv/lib/python3.13/site-packages/sklearn/neural_network/_multilayer_perceptron.py

🟡 **L660** [技术债务]: incorporate sample_weight in sampling here.


### venv/lib/python3.13/site-packages/sklearn/feature_selection/_from_model.py

🟡 **L383** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.

🟡 **L467** [技术债务]: (SLEP6): remove when metadata routing cannot be disabled.


### venv/lib/python3.13/site-packages/sklearn/feature_selection/_univariate_selection.py

🟡 **L372** [技术债务]: for Scipy <= 1.10, `isspmatrix(X)` returns `True` for sparse arrays.

🟡 **L1060** [技术债务]: this class should fit on either p-values or scores,


### venv/lib/python3.13/site-packages/sklearn/inspection/_partial_dependence.py

🟡 **L117** [技术债务]: we should handle missing values (i.e. `np.nan`) specifically and store them


### venv/lib/python3.13/site-packages/sklearn/svm/_base.py

🟡 **L231** [技术债务]: (1.11): remove probability

🟡 **L350** [技术债务]: add keyword copy to copy on demand


### venv/lib/python3.13/site-packages/sklearn/manifold/_mds.py

🟡 **L428** [技术债务]: (1.10): change default `init` to "classical_mds", see PR #32229

🟡 **L429** [技术债务]: (1.10): drop support for boolean `metric`, see PR #32229

🟡 **L430** [技术债务]: (1.10): drop support for `dissimilarity`, see PR #32229


### venv/lib/python3.13/site-packages/sklearn/manifold/_spectral_embedding.py

🟡 **L90** [技术债务]: (jjerphan): Once SciPy 1.11.3 is the minimum supported version, use


### venv/lib/python3.13/site-packages/sklearn/mixture/_base.py

🟡 **L143** [技术债务]: when array API supports __setitem__ with fancy indexing we


### venv/lib/python3.13/site-packages/sklearn/preprocessing/_data.py

🟡 **L2417** [技术债务]: This should be refactored because binarize also calls


### venv/lib/python3.13/site-packages/sklearn/preprocessing/_target_encoder.py

🟡 **L339** [技术债务]: (1.11): remove code block

🟡 **L353** [技术债务]: (1.11): pass shuffle=True to keep backwards compatibility for default


### venv/lib/python3.13/site-packages/sklearn/model_selection/_search.py

🟡 **L902** [技术债务]: (slep006): remove when metadata routing is the only way


### venv/lib/python3.13/site-packages/sklearn/model_selection/__init__.py

🟡 **L51** [技术债务]: remove this check once the estimator is no longer experimental.

🟡 **L97** [技术债务]: remove this check once the estimator is no longer experimental.


### venv/lib/python3.13/site-packages/sklearn/model_selection/_validation.py

🟡 **L337** [技术债务]: (SLEP6): also pass metadata to the predict method for

🟡 **L1189** [技术债务]: (SLEP6): also pass metadata for the predict method.

🟡 **L1649** [技术债务]: (SLEP6): also pass metadata to the predict method for

🟡 **L1985** [技术债务]: (SLEP6): also pass metadata to the predict method for


### venv/lib/python3.13/site-packages/sklearn/model_selection/_search_successive_halving.py

🟡 **L384** [技术债务]: remove this when we add array API support to


### venv/lib/python3.13/site-packages/sklearn/decomposition/_pca.py

🟡 **L564** [技术债务]: remove the following two lines when scikit-learn only depends

🟡 **L617** [技术债务]: remove the following two lines when scikit-learn only

🟡 **L770** [技术债务]: update this code to either:


### venv/lib/python3.13/site-packages/sklearn/decomposition/_dict_learning.py

🟡 **L142** [技术债务]: Make verbosity argument for Lasso?

🟡 **L149** [技术债务]: This parameter should be exposed.

🟡 **L159** [技术债务]: move this handling (which is currently too broad)


### venv/lib/python3.13/site-packages/sklearn/decomposition/_lda.py

🟡 **L459** [技术债务]: make Parallel._effective_n_jobs public instead?


### venv/lib/python3.13/site-packages/sklearn/neighbors/_classification.py

🟡 **L334** [技术债务]: systematize this mapping of metric for

🟡 **L367** [技术债务]: adapt the heuristic for `strategy="auto"` for


### venv/lib/python3.13/site-packages/sklearn/neighbors/_kde.py

🟡 **L41** [技术债务]: create a density estimation base class?


### venv/lib/python3.13/site-packages/sklearn/metrics/cluster/__init__.py

🟡 **L43** [技术债务]: (1.10): Remove


### venv/lib/python3.13/site-packages/sklearn/metrics/cluster/_supervised.py

🟡 **L1307** [技术债务]: (1.10): Remove


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_common.py

🟡 **L394** [技术债务]: Handle multi_class metrics that has a labels argument as well as a

🟡 **L1106** [技术债务]: those metrics doesn't support string label yet


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_dist_metrics.py

🟡 **L80** [技术债务]: Inspect slight numerical discrepancy

🟡 **L164** [技术债务]: Inspect slight numerical discrepancy


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_ranking.py

🟡 **L2607** [技术债务]: (1.11): remove this test


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_pairwise_distances_reduction.py

🟡 **L709** [技术债务]: support CSR matrices without non-zeros elements

🟡 **L716** [技术债务]: support CSR matrices with int64 indices and indptr

🟡 **L913** [技术债务]: introduce assertions on UserWarnings once the Euclidean specialisation


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_classification.py

🟡 **L2948** [技术债务]: (1.11): Remove

🟡 **L3479** [技术债务]: (1.11): Remove


### venv/lib/python3.13/site-packages/sklearn/metrics/_pairwise_distances_reduction/_dispatcher.py

🟡 **L124** [技术债务]: support CSR matrices without non-zeros elements

🟡 **L127** [技术债务]: support CSR matrices with int64 indices and indptr


### venv/lib/python3.13/site-packages/sklearn/metrics/cluster/tests/test_supervised.py

🟡 **L273** [技术债务]: (1.10): Remove


### venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_precision_recall_display.py

🟡 **L678** [技术债务]: (1.10): remove


### venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_det_curve_display.py

🟡 **L116** [技术债务]: (1.10): remove


### venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_common_curve_display.py

🟡 **L800** [技术债务]: (1.10): Remove

🟡 **L816** [技术债务]: (1.11): Remove


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_common.py

🟡 **L253** [技术债务]: we should move this test in `estimator_checks` once we are able


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py

🟡 **L1240** [技术债务]: why is this test brittle ?

🟡 **L1931** [技术债务]: (1.11): remove test with the deprecation of friedman_mse criterion


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_gradient_boosting.py

🟡 **L175** [技术债务]: We temporarily bypass this test. This is due to the fact

🟡 **L691** [技术债务]: the following snippet does not yield the same results on 32 bits


### venv/lib/python3.13/site-packages/sklearn/ensemble/_hist_gradient_boosting/predictor.py

🟡 **L143** [技术债务]: consider always using platform agnostic dtypes for fitted


### venv/lib/python3.13/site-packages/sklearn/ensemble/_hist_gradient_boosting/binning.py

🟡 **L380** [技术债务]: complexity is O(n_categorical_features * 255). Maybe this is


### venv/lib/python3.13/site-packages/sklearn/ensemble/_hist_gradient_boosting/gradient_boosting.py

🟡 **L92** [技术债务]: Ideally this should be computed in parallel over the leaves using something

🟡 **L455** [技术债务]: remove when PDP supports sample weights

🟡 **L565** [技术债务]: incorporate sample_weight in sampling here, as well as

🟡 **L973** [技术债务]: incorporate sample_weights here in `resample`

🟡 **L2114** [技术债务]: This could be done in parallel


### venv/lib/python3.13/site-packages/sklearn/ensemble/_hist_gradient_boosting/tests/test_compare_lightgbm.py

🟡 **L103** [技术债务]: We are not entirely satisfied with this lax comparison, but the root


### venv/lib/python3.13/site-packages/sklearn/cluster/tests/test_affinity_propagation.py

🟡 **L30** [技术债务]: AffinityPropagation must preserve dtype for its fitted attributes


### venv/lib/python3.13/site-packages/sklearn/cluster/tests/test_hdbscan.py

🟡 **L595** [技术债务]: (1.10): remove this test


### venv/lib/python3.13/site-packages/sklearn/cluster/_hdbscan/hdbscan.py

🟡 **L719** [技术债务]: (1.10): remove "warn" option

🟡 **L854** [技术债务]: Benchmark KD vs Ball Tree efficiency


### venv/lib/python3.13/site-packages/sklearn/_loss/tests/test_loss.py

🟡 **L858** [技术债务]: What could we test if loss.approx_hessian?

🟡 **L893** [技术债务]: What could we test if loss.approx_hessian?


### venv/lib/python3.13/site-packages/sklearn/gaussian_process/tests/test_gpr.py

🟡 **L777** [技术债务]: before fitting, the estimator does not have information regarding


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_extra/testing.py

🟡 **L23** [技术债务]: import override from typing (requires Python >=3.12)


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/cupy/_info.py

🟡 **L181** [技术债务]: Does this depend on device?

🟡 **L243** [技术债务]: Does this depend on device?


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/torch/_aliases.py

🟡 **L855** [技术债务]: is the return type a list or a tuple


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/common/_aliases.py

🟡 **L17** [技术债务]: import from typing (requires Python >=3.13)

🟡 **L310** [技术债务]: The standard is not clear about what should happen when x.ndim == 0.

🟡 **L382** [技术债务]: np.clip has other ufunc kwargs


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/common/_helpers.py

🟡 **L42** [技术债务]: import from typing (requires Python >=3.13)

🟡 **L116** [技术债务]: Should we reject ndarray subclasses?

🟡 **L271** [技术债务]: Account for other backends.

🟡 **L300** [技术债务]: drop support for numpy<2 which didn't have __array_namespace__

🟡 **L307** [技术债务]: drop support for jax<0.4.32 which didn't have __array_namespace__

🟡 **L763** [技术债务]: Jitted JAX arrays do not have a device attribute

🟡 **L899** [技术债务]: What if our array is on the GPU already?


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/dask/array/_aliases.py

🟡 **L64** [技术债务]: respect device keyword?

🟡 **L95** [技术债务]: respect device keyword?

🟡 **L159** [技术债务]: respect device keyword?

🟡 **L220** [技术债务]: This won't handle dask unknown shapes


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_compat/dask/array/linalg.py

🟡 **L23** [技术债务]: use the QR wrapper once dask

🟡 **L50** [技术债务]: can't avoid computing U or V for dask


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_extra/_lib/_at.py

🟡 **L23** [技术债务]: import from typing (requires Python >=3.11)


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_extra/_lib/_funcs.py

🟡 **L386** [技术债务]: Benchmark whether this is faster on the NumPy backend:


### venv/lib/python3.13/site-packages/sklearn/externals/array_api_extra/_lib/_utils/_helpers.py

🟡 **L37** [技术债务]: import from typing (requires Python >=3.12 and >=3.13)

🟡 **L328** [技术债务]: https://github.com/pydata/sparse/issues/876

🟡 **L340** [技术债务]: https://github.com/data-apis/array-api/issues/945


### venv/lib/python3.13/site-packages/sklearn/linear_model/_glm/glm.py

🟡 **L238** [技术债务]: if alpha=0 check that X is not rank deficient

🟡 **L418** [技术债务]: Adapt link to User Guide in the docstring, once

🟡 **L422** [技术债务]: make D^2 a score function in module metrics (and thereby get


### venv/lib/python3.13/site-packages/sklearn/linear_model/_glm/_newton_solver.py

🟡 **L405** [技术债务]: :


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py

🟡 **L57** [技术债务]: (1.10): remove filterwarnings for l1_ratios after default changed.

🟡 **L178** [技术债务]: (1.11): remove filterwarnings with change of default scoring

🟡 **L180** [技术债务]: (1.10): remove filterwarnings with deprecation period of use_legacy_attributes

🟡 **L229** [技术债务]: (1.11): remove filterwarnings with change of default scoring

🟡 **L231** [技术债务]: (1.10): remove test with removal of penalty

🟡 **L446** [技术债务]: (1.10): remove because it is default now.

🟡 **L451** [技术债务]: (1.11): remove because it is default now

🟡 **L480** [技术债务]: (1.11): remove filterwarnings with change of default scoring

🟡 **L520** [技术债务]: (1.10): remove with new default of l1_ratios

🟡 **L569** [技术债务]: (1.10) for consistency we may want to adapt _log_reg_scoring_path to

🟡 **L615** [技术债务]: (1.11): remove because it is default now

🟡 **L621** [技术债务]: (1.11): remove because it is default now

🟡 **L646** [技术债务]: (1.11): remove because it is default now

🟡 **L675** [技术债务]: (1.11): remove because it is default now

🟡 **L702** [技术债务]: (1.11): remove because it is default now

🟡 **L925** [技术债务]: (1.11): remove because it is default now

🟡 **L1025** [技术债务]: (1.11): remove because it is default now

🟡 **L1032** [技术债务]: (1.11): remove because it is default now

🟡 **L1069** [技术债务]: (1.11): remove because it is default now

🟡 **L1086** [技术债务]: (1.11): remove because it is default now

🟡 **L1100** [技术债务]: (1.11): remove filterwarnings with change of default scoring

🟡 **L1102** [技术债务]: (1.10): remove filterwarnings with deprecation period of use_legacy_attributes

🟡 **L1404** [技术债务]: (1.11): remove because it is default now

🟡 **L1507** [技术债务]: (1.10): remove l1_ratios because it is default now.

🟡 **L1511** [技术债务]: (1.11): remove because it is default now

🟡 **L1710** [技术债务]: SAGA on sparse data fits the intercept inaccurately with the

🟡 **L1766** [技术债务]: (1.10): remove whole test with the removal of penalty

🟡 **L1894** [技术债务]: (1.11): remove because it is default now

🟡 **L1934** [技术债务]: (1.11): remove because it is default now

🟡 **L1974** [技术债务]: (1.11): remove because it is default now

🟡 **L2005** [技术债务]: (1.11): remove because it is default now

🟡 **L2037** [技术债务]: (1.10): remove whole test with the removal of penalty

🟡 **L2195** [技术债务]: (1.10): remove whole test with the removal of penalty

🟡 **L2227** [技术债务]: (1.10): remove whole test with the removal of penalty

🟡 **L2323** [技术债务]: (1.11): remove because it is default now

🟡 **L2583** [技术债务]: (1.11): remove because it is default now

🟡 **L2637** [技术债务]: (1.11): remove filterwarnings with change of default scoring

🟡 **L2639** [技术债务]: (1.10): remove filterwarnings with deprecation period of use_legacy_attributes

🟡 **L2649** [技术债务]: (1.10): remove after deprecation cycle of penalty.

🟡 **L2666** [技术债务]: (1.11): remove because it is default now

🟡 **L2673** [技术债务]: (1.10): remove after deprecation cycle.

🟡 **L2686** [技术债务]: (1.11): remove because it is default now

🟡 **L2694** [技术债务]: (1.11): remove because it is default now

🟡 **L2791** [技术债务]: those tolerance levels seem quite high. Investigate further if we

🟡 **L2855** [技术债务]: (1.11): remove when default of scoring has changed

🟡 **L2866** [技术债务]: (1.11): remove test when default of scoring has changed

🟡 **L2905** [技术债务]: (callbacks): also test for other solvers when they get supported.

🟡 **L2923** [技术债务]: (callbacks): also test for other solvers when they get supported.

🟡 **L2979** [技术债务]: (1.10): Uncomment when scipy callbacks can be interrupted with StopIteration in

🟡 **L2982** [技术债务]: (callbacks): also test for other solvers when they get supported.

🟡 **L2992** [技术债务]: (callbacks): update/remove as more solvers get supported.


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_sgd.py

🟡 **L527** [技术债务]: (1.10): remove this test


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_common.py

🟡 **L78** [技术债务]: (1.11): remove because it is default now

🟡 **L79** [技术债务]: (1.10): remove because it is default now

🟡 **L225** [技术债务]: (1.10): remove

🟡 **L226** [技术债务]: (1.11): remove


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_ridge.py

🟡 **L329** [技术债务]: `assert_allclose(model.coef_, coef)` should work for all cases but fails

🟡 **L391** [技术债务]: Same as in test_ridge_regression_unpenalized.

🟡 **L446** [技术债务]: Same as in test_ridge_regression_unpenalized.

🟡 **L941** [技术债务]: : test fails on square or tall X

🟡 **L958** [技术债务]: : add `gcv_mode` parameter to RidgeClassifierCV

🟡 **L961** [技术债务]: (1.11) should raises ValueError

🟡 **L1001** [技术债务]: (1.11) should raises ValueError

🟡 **L1139** [技术债务]: (1.11) should raises ValueError

🟡 **L2531** [技术债务]: widening the range of alphas causes failures in the test, in


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_passive_aggressive.py

🟡 **L31** [技术债务]: (1.10): Move to test_sgd.py

🟡 **L139** [技术债务]: (1.10): Move to test_sgd.py

🟡 **L276** [技术债务]: (1.10): Move to test_sgd.py

🟡 **L301** [技术债务]: (1.10): remove


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_least_angle.py

🟡 **L29** [技术债务]: use another dataset that has multiple drops

🟡 **L120** [技术债务]: remove warning filter when numpy min version >= 2.0.0

🟡 **L132** [技术债务]: remove warning filter when numpy min version >= 2.0.0


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_coordinate_descent.py

🟡 **L616** [技术债务]: The high number of iterations are required for convergence and show room

🟡 **L1603** [技术债务]: :

🟡 **L1779** [技术债务]: (1.11): remove


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_base.py

🟡 **L674** [技术债务]: replace this torch/MPS-specific coverage by array-api-strict once


### venv/lib/python3.13/site-packages/sklearn/linear_model/_glm/tests/test_glm.py

🟡 **L385** [技术债务]: `assert_allclose(model.coef_, coef)` should work for all cases but fails


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_pprint.py

🟡 **L287** [技术债务]: (1.11): remove because it is default now


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_stats.py

🟡 **L431** [技术债务]: remove the following skip once no longer applicable.

🟡 **L469** [技术债务]: remove the following skip once no longer applicable.


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_validation.py

🟡 **L22** [技术债务]: add this estimator into the _mocking module in a further refactoring


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_estimator_checks.py

🟡 **L1480** [技术债务]: this test should be uncommented when the checks will be granular


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_array_api.py

🟡 **L385** [技术债务]: add cupy to the list of libraries once the following upstream issue

🟡 **L1014** [技术债务]: replace this torch/MPS-specific coverage by array-api-strict once


### venv/lib/python3.13/site-packages/sklearn/utils/_test_common/instance_generator.py

🟡 **L359** [技术债务]: (1.11): remove scoring because it is default now

🟡 **L519** [技术债务]: (devtools): allow third-party developers to pass test specific params to checks

🟡 **L521** [技术债务]: (devtools): check that function names here exist in checks for the estimator

🟡 **L615** [技术债务]: dual=True is a stochastic solver: we cannot rely on

🟡 **L874** [技术债务]: (devtools): enable this behavior for third party estimators as well

🟡 **L903** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L912** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L921** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L930** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L946** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L998** [技术债务]: investigate failure see meta-issue #16298

🟡 **L1007** [技术债务]: investigate failure see meta-issue #16298

🟡 **L1042** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1051** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1060** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1077** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1095** [技术债务]: replace by a statistical test when _dual=True, see meta-issue #16298

🟡 **L1107** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1128** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1139** [技术债务]: replace by a statistical test when probability=True

🟡 **L1180** [技术债务]: see gh-33205 for details

🟡 **L1185** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1214** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1221** [技术债务]: error raised by all zero sample weights will be addressed by PR #31529

🟡 **L1227** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1240** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1249** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1274** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1283** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1292** [技术债务]: replace by a statistical test, see meta-issue #16298

🟡 **L1328** [技术债务]: replace by a statistical test when probability=True

🟡 **L1356** [技术债务]: remove when scipy min version >= 1.11

🟡 **L1394** [技术债务]: remove when scipy min version >= 1.16


### venv/lib/python3.13/site-packages/sklearn/feature_selection/tests/test_from_model.py

🟡 **L472** [技术债务]: we cannot validate the upper bound of the attribute at transform


### venv/lib/python3.13/site-packages/sklearn/inspection/tests/test_partial_dependence.py

🟡 **L680** [技术债务]: extend to HistGradientBoosting once sample_weight is supported


### venv/lib/python3.13/site-packages/sklearn/inspection/_plot/tests/test_boundary_decision_display.py

🟡 **L780** [技术债务]: Remove version check and the else branch once 3.10 is the minimal

🟡 **L810** [技术债务]: Remove version check and the else branch once 3.10 is the minimal


### venv/lib/python3.13/site-packages/sklearn/svm/tests/test_sparse.py

🟡 **L97** [技术债务]: (1.11): remove probability=True and adapt check_svm_model_equal accordingly.

🟡 **L127** [技术债务]: (1.11): remove probability=True and calls to predict_proba.

🟡 **L465** [技术债务]: (1.11): remove probability=True and calls to predict_proba.


### venv/lib/python3.13/site-packages/sklearn/svm/tests/test_svm.py

🟡 **L69** [技术债务]: investigate why assertion on L148 fails.

🟡 **L325** [技术债务]: rework this test to be independent of the random seeds.

🟡 **L382** [技术债务]: (1.11): remove this test entirely

🟡 **L504** [技术债务]: rework this test to be independent of the random seeds.

🟡 **L683** [技术债务]: rework this test to be independent of the random seeds.

🟡 **L1170** [技术债务]: (1.11): remove test entirely.


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_isomap.py

🟡 **L148** [技术债务]: check that it actually does something useful

🟡 **L234** [技术债务]: compare results on dense and sparse data as proposed in:


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_mds.py

🟡 **L142** [技术债务]: (1.10): remove warning filter

🟡 **L156** [技术债务]: (1.10): remove warning filter

🟡 **L195** [技术债务]: (1.10): remove warning filter

🟡 **L222** [技术债务]: (1.10): remove warning filter

🟡 **L245** [技术债务]: (1.10): delete this test


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_t_sne.py

🟡 **L321** [技术债务]: compare results on dense and sparse data as proposed in:

🟡 **L1020** [技术债务]: re-enable this test if/when `manhattan_distances` is refactored to


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_spectral_embedding.py

🟡 **L128** [技术债务]: investigate why this test is seed-sensitive on 32-bit Python


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_locally_linear.py

🟡 **L48** [技术债务]: rewrite this test to make less sensitive to the random seed,

🟡 **L121** [技术债务]: check that it actually does something useful


### venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_common.py

🟡 **L99** [技术债务]: we can introduce equal_nan=True in recent version of numpy.


### venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_discretization.py

🟡 **L492** [技术债务]: change to averaged inverted cdf, but that means we only get bin


### venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_data.py

🟡 **L817** [技术债务]: replace this torch/MPS-specific coverage by array-api-strict once

🟡 **L831** [技术债务]: replace this torch/MPS-specific coverage by array-api-strict once


### venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_target_encoder.py

🟡 **L726** [技术债务]: remove this workaround when pandas 4 is our minimum version

🟡 **L765** [技术债务]: (1.11): remove after deprecation


### venv/lib/python3.13/site-packages/sklearn/callback/tests/test_callback_context.py

🟡 **L375** [技术债务]: (callbacks): should be a common test in a dev test suite instead of a check

🟡 **L454** [技术债务]: (callbacks): check that the reconstructed estimator can be used to predict


### venv/lib/python3.13/site-packages/sklearn/model_selection/tests/test_search.py

🟡 **L2550** [技术债务]: Replace this test with a full `check_estimator` once we have API only


### venv/lib/python3.13/site-packages/sklearn/decomposition/tests/test_nmf.py

🟡 **L992** [技术债务]: use the provided W when init="custom".


### venv/lib/python3.13/site-packages/sklearn/decomposition/tests/test_pca.py

🟡 **L580** [技术债务]: explain what this is testing

🟡 **L597** [技术债务]: explain what this is testing


### venv/lib/python3.13/site-packages/sklearn/cross_decomposition/tests/test_pls.py

🟡 **L78** [技术债务]: one would expect y_trans == pls.y_scores_ but this is not


### venv/lib/python3.13/site-packages/sklearn/neighbors/tests/test_lof.py

🟡 **L252** [技术债务]: compare results on dense and sparse data as proposed in:


### venv/lib/python3.13/site-packages/sklearn/neighbors/tests/test_neighbors.py

🟡 **L381** [技术债务]: also test radius_neighbors, but requires different assertion

🟡 **L1626** [技术债务]: remove when NearestNeighbors methods uses parameter validation mechanism

🟡 **L1730** [技术债务]: Remove ignore_warnings when minimum supported SciPy version is 1.17

🟡 **L2259** [技术债务]: Remove ignore_warnings when minimum supported SciPy version is 1.17

🟡 **L2494** [技术债务]: if score is refactored to evaluate models for other scoring


### venv/lib/python3.13/site-packages/joblib/test/common.py

🟡 **L18** [技术债务]: straight removal since in joblib.test.common?

🟡 **L44** [技术债务]: Turn this back on after refactoring yield based tests in test_hashing


### venv/lib/python3.13/site-packages/joblib/test/test_memory.py

🟡 **L146** [技术债务]: test that the cache related to the function cache persists across

🟡 **L170** [技术债务]: when Python 3.11 is the minimum supported version, use


### venv/lib/python3.13/site-packages/joblib/externals/cloudpickle/cloudpickle.py

🟡 **L1349** [技术债务]: decorrelate reducer_override (which is tied to CPython's


### venv/lib/python3.13/site-packages/joblib/externals/loky/_base.py

🟡 **L20** [技术债务]: investigate why using `concurrent.futures.Future` directly does not


### venv/lib/python3.13/site-packages/joblib/externals/loky/backend/synchronize.py

🟡 **L11** [技术债务]: investigate which Python version is required to be able to use


### venv/lib/python3.13/site-packages/prompt_toolkit/lexers/pygments.py

🟡 **L120** [技术债务]: Add definitions for other languages.


### venv/lib/python3.13/site-packages/prompt_toolkit/layout/containers.py

🟡 **L2581** [技术债务]: not entirely correct yet in case of line wrapping and long lines.


### venv/lib/python3.13/site-packages/prompt_toolkit/layout/utils.py

🟡 **L37** [技术债务]: When creating a copy() or [:], return also an _ExplodedList.


### venv/lib/python3.13/site-packages/prompt_toolkit/layout/scrollable_pane.py

🟡 **L342** [技术债务]: if the window is only partly visible, then truncate width/height.


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/named_commands.py

🟡 **L582** [技术债务]: Make the format suitable for the inputrc file.


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/scroll.py

🟡 **L142** [技术债务]: not entirely correct yet, in case of line wrapping and many long lines.


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/vi.py

🟡 **L1081** [技术债务]: go to begin of sentence.

🟡 **L1087** [技术债务]: go to end of sentence.

🟡 **L1362** [技术债务]: 'dat', 'dit', (tags (like xml)


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/emacs.py

🟡 **L191** [技术债务]: :

🟡 **L196** [技术债务]: :


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/mouse.py

🟡 **L205** [技术债务]: Is it possible to add modifiers here?


### venv/lib/python3.13/site-packages/narwhals/_polars/dataframe.py

🟡 **L479** [技术债务]: (marco): we can delete this branch after Polars==0.20.30 becomes the minimum


### venv/lib/python3.13/site-packages/narwhals/_polars/expr.py

🟡 **L51** [技术债务]: @dangotbanned: Remove in #2713


### venv/lib/python3.13/site-packages/narwhals/_arrow/dataframe.py

🟡 **L824** [技术债务]: (Unassigned): Even with promote_options="permissive", pyarrow does not


### venv/lib/python3.13/site-packages/narwhals/_arrow/series.py

🟡 **L88** [技术债务]: @dangotbanned: move into `_arrow.utils`

🟡 **L732** [技术债务]: (marco): `pc.unique` seems to always maintain order, is that guaranteed?


### venv/lib/python3.13/site-packages/narwhals/_arrow/group_by.py

🟡 **L129** [技术债务]: (unassigned): combine with `return` above once PyArrow 15 is the minimum.


### venv/lib/python3.13/site-packages/narwhals/_arrow/utils.py

🟡 **L328** [技术债务]: @dangotbanned: Use a `TypeVar` in guards


### venv/lib/python3.13/site-packages/narwhals/_arrow/expr.py

🟡 **L119** [技术债务]: (marco): is there a way to do this efficiently without


### venv/lib/python3.13/site-packages/narwhals/_duckdb/utils.py

🟡 **L294** [技术债务]: (unassigned): cover once https://github.com/narwhals-dev/narwhals/issues/2742 addressed

🟡 **L365** [技术债务]: (unassigned): Replace with `duckdb.WindowExpression` when they release it.


### venv/lib/python3.13/site-packages/narwhals/_duckdb/namespace.py

🟡 **L98** [技术债务]: (unassigned): use relational API when available https://github.com/duckdb/duckdb/discussions/16996


### venv/lib/python3.13/site-packages/narwhals/_pandas_like/dataframe.py

🟡 **L734** [技术债务]: (FBruzzesi): See https://github.com/modin-project/modin/issues/7384


### venv/lib/python3.13/site-packages/narwhals/_pandas_like/series.py

🟡 **L582** [技术债务]: (Unassigned): If/when pandas exposes an API which distinguishes NaN vs null, use that.

🟡 **L619** [技术债务]: (Unassigned): https://github.com/narwhals-dev/narwhals/issues/3231


### venv/lib/python3.13/site-packages/narwhals/_pandas_like/utils.py

🟡 **L204** [技术债务]: @dangotbanned: Investigate how we could handle `cudf` without `str(native_dtype)`

🟡 **L386** [技术债务]: (Unassigned): is there no pyarrow-backed categorical?

🟡 **L698** [技术债务]: (FBruzzesi): Should we pass the `copy=False` flag?


### venv/lib/python3.13/site-packages/narwhals/_spark_like/utils.py

🟡 **L94** [技术债务]: (marco): cover this

🟡 **L180** [技术债务]: (unassigned): cover once https://github.com/narwhals-dev/narwhals/issues/2742 addressed


### venv/lib/python3.13/site-packages/narwhals/stable/v1/dependencies.py

🟡 **L59** [技术债务]: (Unassigned): For duckdb and ibis backends:


### venv/lib/python3.13/site-packages/fastapi/dependencies/utils.py

🟡 **L595** [技术债务]: remove this parameter later, no longer used, not removing it yet as some


### venv/lib/python3.13/site-packages/fastapi/openapi/utils.py

🟡 **L409** [技术债务]: probably make status_code a default class attribute for all


### venv/lib/python3.13/site-packages/fastapi/_compat/shared.py

🟡 **L187** [技术债务]: remove this function once the required version of Pydantic fully

🟡 **L199** [技术债务]: remove this function once the required version of Pydantic fully


### venv/lib/python3.13/site-packages/fastapi/_compat/v2.py

🟡 **L58** [技术债务]: remove when this is merged (or equivalent): https://github.com/pydantic/pydantic/pull/12841

🟡 **L73** [技术债务]: remove when dropping support for Pydantic < v2.12.3

🟡 **L99** [技术债务]: remove when dropping support for Pydantic < v2.12.3

🟡 **L153** [技术债务]: remove after setting the min Pydantic to v2.12.3

🟡 **L277** [技术债务]: remove when deprecating Pydantic v1


### venv/lib/python3.13/site-packages/arch/bootstrap/base.py

🟡 **L193** [技术债务]: This should use overload ensure2d definitions to know it is ndarray


### venv/lib/python3.13/site-packages/arch/unitroot/cointegration.py

🟡 **L755** [技术债务]: Rank check and drop??


### venv/lib/python3.13/site-packages/arch/univariate/mean.py

🟡 **L1039** [技术债务]: This is not tested, but probably right


### venv/lib/python3.13/site-packages/arch/univariate/volatility.py

🟡 **L767** [技术债务]: This looks like a design flaw.It is optional above but then must


### venv/lib/python3.13/site-packages/arch/utility/array.py

🟡 **L342** [技术债务]: Bug in pandas-stubs does not return correct types when errors=coerce


### venv/lib/python3.13/site-packages/arch/tests/unitroot/test_fmols_ccr.py

🟡 **L329** [技术债务]: Determine reason for difference here


### venv/lib/python3.13/site-packages/arch/tests/unitroot/test_unitroot.py

🟡 **L1** [技术债务]: Tests for features that are just called

🟡 **L2** [技术债务]: Test for trend='ctt'

🟡 **L302** [技术债务]: Currently not a test, just makes sure code runs at all


### venv/lib/python3.13/site-packages/arch/tests/univariate/test_volatility.py

🟡 **L923** [技术债务]: Test variance fit by RM06

🟡 **L932** [技术债务]: Test RM06 Simulation


### venv/lib/python3.13/site-packages/arch/tests/univariate/test_variance_forecasting.py

🟡 **L1277** [技术债务]: This is not correct.  Should be (900,5)


### venv/lib/python3.13/site-packages/arch/unitroot/critical_values/simulation/phillips-ouliaris-simulation-process.py

🟡 **L162** [技术债务]: Bug in pandas-stubs prevents valid index types

🟡 **L179** [技术债务]: Bug in pandas-stubs prevents valid index types

🟡 **L215** [技术债务]: Bug in pandas-stubs prevents valid index types

🟡 **L217** [技术债务]: Bug in pandas-stubs prevents valid index types


### venv/lib/python3.13/site-packages/curl_cffi/requests/impersonate.py

🟡 **L127** [技术债务]: remove in version 1.x


### venv/lib/python3.13/site-packages/curl_cffi/requests/websockets.py

🟡 **L599** [技术债务]: Reconnect logic

🟡 **L659** [技术债务]: As per spec, we should wait for the server to close the connection


### venv/lib/python3.13/site-packages/curl_cffi/requests/session.py

🟡 **L1089** [技术债务]: -> Self


### venv/lib/python3.13/site-packages/curl_cffi/requests/utils.py

🟡 **L216** [技术债务]: should we move this function to headers.py?


### venv/lib/python3.13/site-packages/curl_cffi/requests/exceptions.py

🟡 **L160** [技术债务]: use this warning as a base


### venv/lib/python3.13/site-packages/tensorboard/backend/process_graph.py

🟡 **L42** [技术债务]: (@davidsoergel): detect whether a graph has been filtered already


### venv/lib/python3.13/site-packages/tensorboard/backend/http_util.py

🟡 **L32** [技术债务]: (stephanwlee): Refactor this to not use the module variable but


### venv/lib/python3.13/site-packages/tensorboard/backend/application.py

🟡 **L231** [技术债务]: (@chihuahua): Delete this RPC once we have skylark rules that


### venv/lib/python3.13/site-packages/tensorboard/backend/security_validator.py

🟡 **L38** [技术债务]: (stephanwlee): remove it eventually.

🟡 **L61** [技术债务]: (3.x): raise a value error.

🟡 **L145** [技术债务]: (stephanwlee): allow configuration for whitelist of domains for

🟡 **L147** [技术债务]: (stephanwlee): deprecate the sha-based whitelisting.


### venv/lib/python3.13/site-packages/tensorboard/summary/_output.py

🟡 **L101** [技术债务]: (#4581): cache summary metadata to emit only once.


### venv/lib/python3.13/site-packages/tensorboard/compat/tensorflow_stub/dtypes.py

🟡 **L75** [技术债务]: (mrry): Make the necessary changes (using __new__) to ensure

🟡 **L539** [技术债务]: (mrry,keveman): Investigate Numpy type registration to replace this

🟡 **L575** [技术债务]: (#1677): _np_bfloat16 is defined as 0. This causes `as_dtype` to


### venv/lib/python3.13/site-packages/tensorboard/compat/tensorflow_stub/tensor_shape.py

🟡 **L523** [技术债务]: (irving): Eliminate the single integer special case.

🟡 **L636** [技术债务]: (mrry): Handle these maybe.

🟡 **L645** [技术债务]: (mrry): Handle this better, as it will be useful for handling

🟡 **L711** [技术债务]: (mrry): Handle the case where we concatenate a known shape with a


### venv/lib/python3.13/site-packages/tensorboard/compat/tensorflow_stub/errors.py

🟡 **L103** [技术债务]: (mrry): Consider computing the actual longest common subsequence.

🟡 **L499** [技术债务]: (b/77295559): expand use of TF_Status* SWIG typemap and deprecate this.


### venv/lib/python3.13/site-packages/tensorboard/compat/tensorflow_stub/pywrap_tensorflow.py

🟡 **L187** [技术债务]: Handle gzip and zlib compressed files


### venv/lib/python3.13/site-packages/tensorboard/compat/tensorflow_stub/io/gfile.py

🟡 **L284** [技术债务]: (orionr): This endpoint risks splitting a multi-byte

🟡 **L351** [技术债务]: Remove and instead handle in GetLogdirSubdirectories.


### venv/lib/python3.13/site-packages/tensorboard/_vendor/bleach/linkifier.py

🟡 **L267** [技术债务]: (willkg): This is a terrible idea. What it does is drop all the


### venv/lib/python3.13/site-packages/tensorboard/_vendor/bleach/html5lib_shim.py

🟡 **L638** [技术债务]: (willkg): Do we want to make sure these are valid number


### venv/lib/python3.13/site-packages/tensorboard/_vendor/bleach/sanitizer.py

🟡 **L153** [技术债务]: (willkg): this doesn't handle when attributes or an

🟡 **L587** [技术债务]: (willkg): if style is allowed, but no


### venv/lib/python3.13/site-packages/tensorboard/_vendor/bleach/_vendor/html5lib/serializer.py

🟡 **L302** [技术债务]: Add namespace support here


### venv/lib/python3.13/site-packages/tensorboard/_vendor/bleach/_vendor/html5lib/treeadapters/genshi.py

🟡 **L51** [技术债务]: What to do?


### venv/lib/python3.13/site-packages/tensorboard/plugins/core/core_plugin.py

🟡 **L229** [技术债务]: (chihuahua): Remove this method once the frontend instead uses the

🟡 **L240** [技术债务]: (chihuahua): Remove this method once the frontend instead uses the


### venv/lib/python3.13/site-packages/tensorboard/plugins/graph/graphs_plugin.py

🟡 **L73** [技术债务]: (@chihuahua): Reconcile this setting with Health Pills.


### venv/lib/python3.13/site-packages/tensorboard/plugins/distribution/compressor.py

🟡 **L47** [技术债务]: (@jart): Unfork these methods.


### venv/lib/python3.13/site-packages/tensorboard/plugins/image/summary_v2.py

🟡 **L99** [技术债务]: (https://github.com/tensorflow/tensorboard/issues/2109): remove fallback


### venv/lib/python3.13/site-packages/tensorboard/plugins/hparams/summary_v2.py

🟡 **L422** [技术债务]: (#1998): Add int dtype.

🟡 **L536** [技术债务]: (#1998): Add int dtype.


### venv/lib/python3.13/site-packages/tensorboard/plugins/hparams/backend_context.py

🟡 **L373** [技术债务]: Support old return value of Collection[provider.Hyperparameters]


### venv/lib/python3.13/site-packages/tensorboard/plugins/audio/summary_v2.py

🟡 **L89** [技术债务]: (https://github.com/tensorflow/tensorboard/issues/2109): remove fallback


### venv/lib/python3.13/site-packages/tensorboard/plugins/audio/audio_plugin.py

🟡 **L196** [技术债务]: (@wchargin): Move this call from `/audio` (called many


### venv/lib/python3.13/site-packages/tensorboard/plugins/debugger_v2/debug_data_provider.py

🟡 **L230** [技术债务]: (cais): Support parsing trace_id when it is supported.

🟡 **L280** [技术债务]: (cais): Support parsing trace_id when it is supported.


### venv/lib/python3.13/site-packages/tensorboard/plugins/debugger_v2/debug_data_multiplexer.py

🟡 **L26** [技术债务]: (cais): When tfdbg2 allows there to be multiple DebugEvent file sets in

🟡 **L73** [技术债务]: (cais): Replace this with Alert.to_json() when supported by the

🟡 **L82** [技术债务]: (cais): Once supported by backend, add 'op_name' key

🟡 **L147** [技术债务]: (cais): Avoid conditional imports and instead use

🟡 **L258** [技术债务]: (cais): Add the semantically meaningful tag names such as

🟡 **L300** [技术债务]: (cais): This should generate a 400 response instead.

🟡 **L310** [技术债务]: (cais): Replace this with Alert.to_json() when

🟡 **L352** [技术债务]: (cais): For scalability, use begin and end kwargs when available in

🟡 **L556** [技术债务]: (cais): "num_outputs" should be populated in to_json() instead.

🟡 **L627** [技术债务]: (cais): Use public method (`stack_frame_by_id()`) when


### venv/lib/python3.13/site-packages/tensorboard/plugins/text/summary_v2.py

🟡 **L88** [技术债务]: (https://github.com/tensorflow/tensorboard/issues/2109): remove fallback


### venv/lib/python3.13/site-packages/tensorboard/plugins/scalar/summary_v2.py

🟡 **L82** [技术债务]: (https://github.com/tensorflow/tensorboard/issues/2109): remove fallback


### venv/lib/python3.13/site-packages/tensorboard/plugins/histogram/summary_v2.py

🟡 **L178** [技术债务]: (https://github.com/tensorflow/tensorboard/issues/2109): remove fallback

🟡 **L184** [技术债务]: (ytjing): add special case handling.


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_file_inspector.py

🟡 **L327** [技术债务]: Consider changing this to only check for out-of-order


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/data_ingester.py

🟡 **L40** [技术债务]: (@wchargin): Replace with something that works for third-party plugins.


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_file_loader.py

🟡 **L66** [技术债务]: (#1711): Eventually remove PyRecordReader fallback once we can drop


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/plugin_event_multiplexer.py

🟡 **L153** [技术债务]: (@decentralion) - Make it impossible to overwrite an old path


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_multiplexer.py

🟡 **L127** [技术债务]: (@decentralion) - Make it impossible to overwrite an old path


### venv/lib/python3.13/site-packages/sb3_contrib/common/maskable/policies.py

🟡 **L216** [技术债务]: check for features_extractor


### venv/lib/python3.13/site-packages/matplotlib/tri/_tripcolor.py

🟡 **L166** [技术债务]: check whether the above explicit limit handling can be


### venv/lib/python3.13/site-packages/matplotlib/axes/_axes.py

🟡 **L3337** [技术债务]: do we want to be more restrictive and check lengths?


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_qt.py

🟡 **L500** [技术债务]: queued signal connection might be safer than singleShot


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_pdf.py

🟡 **L86** [技术债务]: s:

🟡 **L1043** [技术债务]: serif

🟡 **L1046** [技术债务]: symbolic (most TeX fonts are)

🟡 **L1055** [技术债务]: all caps

🟡 **L1058** [技术债务]: small caps

🟡 **L1061** [技术债务]: force bold

🟡 **L1081** [技术债务]: find this out

🟡 **L1082** [技术债务]: this one too

🟡 **L1347** [技术债务]: serif

🟡 **L1355** [技术债务]: all caps

🟡 **L1357** [技术债务]: small caps

🟡 **L1359** [技术债务]: force bold

🟡 **L2298** [技术债务]: combine consecutive texts into one BT/ET delimited section


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_pgf.py

🟡 **L739** [技术债务]: this should be latex_pt_to_in instead of mpl_pt_to_in


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_mixed.py

🟡 **L104** [技术债务]: If the mixedmode resolution differs from the figure's


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_gtk4.py

🟡 **L265** [技术债务]: Only update the rubberband area.


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_gtk3.py

🟡 **L244** [技术债务]: Only update the rubberband area.


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_wx.py

🟡 **L271** [技术债务]: It may be wise to cache font information


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_agg.py

🟡 **L273** [技术债务]: , handle props, angle, origins


### venv/lib/python3.13/site-packages/matplotlib/tests/test_simplification.py

🟡 **L178** [技术债务]: guarantee offset > 0 results in some offsets < 0


### venv/lib/python3.13/site-packages/matplotlib/tests/test_backends_interactive.py

🟡 **L295** [技术债务]: debug why WX needs this only on py >= 3.8


### venv/lib/python3.13/site-packages/matplotlib/tests/test_subplots.py

🟡 **L176** [技术债务]: should this test more options?


### venv/lib/python3.13/site-packages/matplotlib/tests/test_image.py

🟡 **L1994** [技术债务]: The second and third panels in the bottom row show that the handling of


### venv/lib/python3.13/site-packages/matplotlib/tests/test_datetime.py

🟡 **L846** [技术债务]: It should be possible for positions to be datetimes too


### venv/lib/python3.13/site-packages/matplotlib/tests/test_widgets.py

🟡 **L1238** [技术债务]: Axes.scatter promotes facecolor to edgecolor on unfilled markers,


### venv/lib/python3.13/site-packages/matplotlib/tests/test_contour.py

🟡 **L424** [技术债务]: Force tick locations for now for backcompat with old test


### venv/lib/python3.13/site-packages/prometheus_client/openmetrics/parser.py

🟡 **L503** [技术债务]: check labelvalues are valid utf8


### venv/lib/python3.13/site-packages/alembic/util/pyfiles.py

🟡 **L60** [技术债务]: there seem to be zero tests for the package resource codepath


### venv/lib/python3.13/site-packages/alembic/ddl/postgresql.py

🟡 **L146** [技术债务]: this seems quite a bad idea for a default that's a SQL


### venv/lib/python3.13/site-packages/alembic/ddl/mssql.py

🟡 **L153** [技术债务]: see why these two alter_columns can't be called

🟡 **L389** [技术债务]: there can also be a named constraint


### venv/lib/python3.13/site-packages/alembic/ddl/mysql.py

🟡 **L225** [技术债务]: this is not really covered anymore ?

🟡 **L289** [技术债务]: if SQLA 1.0, make use of "duplicates_index"


### venv/lib/python3.13/site-packages/alembic/runtime/migration.py

🟡 **L1311** [技术债务]: we probably need to look for self.to_ inside of heads,


### venv/lib/python3.13/site-packages/alembic/operations/schemaobj.py

🟡 **L135** [技术债务]: need event tests to ensure the event


### venv/lib/python3.13/site-packages/alembic/operations/batch.py

🟡 **L266** [技术债务]: we are skipping unnamed reflected CheckConstraint


### venv/lib/python3.13/site-packages/alembic/operations/ops.py

🟡 **L1823** [技术债务]: make this a little simpler


### venv/lib/python3.13/site-packages/alembic/testing/util.py

🟡 **L96** [技术债务]: :


### venv/lib/python3.13/site-packages/alembic/testing/schemacompare.py

🟡 **L25** [技术债务]: compare constraints, indexes

🟡 **L40** [技术债务]: datatypes etc


### venv/lib/python3.13/site-packages/alembic/testing/fixtures.py

🟡 **L264** [技术债务]: make this more flexible about

🟡 **L357** [技术债务]: conditional comment support


### venv/lib/python3.13/site-packages/alembic/autogenerate/render.py

🟡 **L795** [技术债务]: for non-ascii colname, assign a "key"


### venv/lib/python3.13/site-packages/alembic/autogenerate/compare/constraints.py

🟡 **L404** [技术债务]: for plugins, let's do is_index_sig / is_uq_sig


### venv/lib/python3.13/site-packages/numba/experimental/structref.py

🟡 **L302** [技术债务]: mostly the same as jitclass ctor_impl()


### venv/lib/python3.13/site-packages/numba/core/dispatcher.py

🟡 **L1056** [技术债务]: refactor this to not assume on `cpu_target`


### venv/lib/python3.13/site-packages/numba/core/transforms.py

🟡 **L737** [技术债务]: this should be a comparison in topological order, right


### venv/lib/python3.13/site-packages/numba/core/compiler_machinery.py

🟡 **L173** [技术债务]: Eventually enable this, it enforces self consistency after each pass

🟡 **L321** [技术债务]: Add in self consistency enforcement for


### venv/lib/python3.13/site-packages/numba/core/inline_closurecall.py

🟡 **L762** [技术债务]: handle stararg

🟡 **L775** [技术债务]: handle arguments for make_function case similar to function


### venv/lib/python3.13/site-packages/numba/core/ir_utils.py

🟡 **L645** [技术债务]: find mutable args that are not definitely assigned instead of

🟡 **L688** [技术债务]: remove other nodes like SetItem etc.

🟡 **L839** [技术债务]: keep definitions up-to-date to avoid the need for rebuilding

🟡 **L874** [技术债务]: sometimes gufunc backend creates duplicate code

🟡 **L917** [技术债务]: add more immutable types

🟡 **L1820** [技术债务]: get this from diagnostics store

🟡 **L1826** [技术债务]: DO NOT ADD MORE THINGS HERE!


### venv/lib/python3.13/site-packages/numba/core/old_boxing.py

🟡 **L481** [技术债务]: check matching dtype.

🟡 **L494** [技术债务]: here we have minimal typechecking by the itemsize.


### venv/lib/python3.13/site-packages/numba/core/lowering.py

🟡 **L743** [技术债务]: is this looks dodgy ...


### venv/lib/python3.13/site-packages/numba/core/new_boxing.py

🟡 **L532** [技术债务]: check matching dtype.

🟡 **L545** [技术债务]: here we have minimal typechecking by the itemsize.


### venv/lib/python3.13/site-packages/numba/core/object_mode_passes.py

🟡 **L84** [技术债务]: move this


### venv/lib/python3.13/site-packages/numba/core/interpreter.py

🟡 **L2619** [技术债务]: refactor this pattern. occurred several times.

🟡 **L2988** [技术债务]: just a lazy hack

🟡 **L2998** [技术债务]: fifth lowest bit now indicates a forced version to bool.


### venv/lib/python3.13/site-packages/numba/core/debuginfo.py

🟡 **L146** [技术债务]: Is there a better way of determining "this is a complex


### venv/lib/python3.13/site-packages/numba/core/typed_passes.py

🟡 **L489** [技术债务]: move this

🟡 **L898** [技术债务]: move this into PostProcessor


### venv/lib/python3.13/site-packages/numba/core/untyped_passes.py

🟡 **L1055** [技术债务]: check the loop head has literal_unroll, if it does but


### venv/lib/python3.13/site-packages/numba/core/codegen.py

🟡 **L392** [技术债务]: :

🟡 **L742** [技术债务]: we shouldn't need to recreate the LLVM module object


### venv/lib/python3.13/site-packages/numba/core/target_extension.py

🟡 **L58** [技术债务]: Should this logic be reversed to prefer TLS override?


### venv/lib/python3.13/site-packages/numba/core/controlflow.py

🟡 **L896** [技术债务]: Looplifting requires the loop entry be its own block.

🟡 **L906** [技术债务]: WithLifting requires the loop entry be its own block.


### venv/lib/python3.13/site-packages/numba/core/extending.py

🟡 **L126** [技术债务]: abort now if the kwarg 'target' relates to an unregistered target,


### venv/lib/python3.13/site-packages/numba/cloudpickle/cloudpickle.py

🟡 **L1301** [技术债务]: decorrelate reducer_override (which is tied to CPython's


### venv/lib/python3.13/site-packages/numba/cuda/vector_types.py

🟡 **L160** [技术债务]: speed up with memoization


### venv/lib/python3.13/site-packages/numba/cuda/cudaimpl.py

🟡 **L511** [技术债务]: the llvm.bitreverse.i32 intrinsic isn't supported by nvcc

🟡 **L523** [技术债务]: the llvm.bitreverse.i64 intrinsic isn't supported by nvcc


### venv/lib/python3.13/site-packages/numba/stencils/stencilparfor.py

🟡 **L246** [技术债务]: Loosen this restriction to adhere to casting rules.

🟡 **L413** [技术债务]: Loosen this restriction to adhere to casting rules.


### venv/lib/python3.13/site-packages/numba/tests/test_parallel_backend.py

🟡 **L33** [技术债务]: Put this in a subprocess so the address space is kept clean


### venv/lib/python3.13/site-packages/numba/tests/support.py

🟡 **L1239** [技术债务]: add a way to not do this! un-finalizing is not a good idea


### venv/lib/python3.13/site-packages/numba/tests/test_np_functions.py

🟡 **L2032** [技术债务]: Contiguity of result not consistent with numpy

🟡 **L2049** [技术债务]: Contiguity of result not consistent with numpy


### venv/lib/python3.13/site-packages/numba/tests/test_operators.py

🟡 **L687** [技术债务]: native handling of 0 ** negative power


### venv/lib/python3.13/site-packages/numba/tests/test_comprehension.py

🟡 **L219** [技术债务]: we can't really assert the error message for the above


### venv/lib/python3.13/site-packages/numba/tests/test_np_randomgen.py

🟡 **L17** [技术债务]: Following testing tolerance adjustments should be reduced


### venv/lib/python3.13/site-packages/numba/tests/test_indexing.py

🟡 **L712** [技术债务]: should be enable to handle this in NoPython mode


### venv/lib/python3.13/site-packages/numba/tests/test_array_methods.py

🟡 **L1648** [技术债务]: scalars are not tested (issue #3469)

🟡 **L1675** [技术债务]: scalars are not tested (issue #3469)


### venv/lib/python3.13/site-packages/numba/tests/test_stencils.py

🟡 **L509** [技术债务]: ValueError should be thrown instead of LoweringError


### venv/lib/python3.13/site-packages/numba/tests/test_svml.py

🟡 **L32** [技术债务]: [] and comments below mean unused/untested SVML function, it's to be

🟡 **L35** [技术债务]: this test does not support functions with more than 1 arguments yet

🟡 **L81** [技术债务]: these functions are not vectorizable with complex types

🟡 **L112** [技术债务]: refactor so this for-loop goes into umbrella function,

🟡 **L114** [技术债务]: it will enable mixed usecases like prange + numpy

🟡 **L192** [技术债务]: address skipped tests below


### venv/lib/python3.13/site-packages/numba/tests/test_lists.py

🟡 **L1136** [技术债务]: this triggers a reflection error.

🟡 **L1205** [技术债务]: this triggers a reflection error.


### venv/lib/python3.13/site-packages/numba/tests/test_typedlist.py

🟡 **L1138** [技术债务]: comparison of empty array-typed lists fails

🟡 **L1629** [技术债务]: this bails with a length casting error when we attempt to


### venv/lib/python3.13/site-packages/numba/tests/test_boundscheck.py

🟡 **L40** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L57** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L84** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L140** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L157** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L179** [技术债务]: When we raise the same error message as numpy, test that

🟡 **L200** [技术债务]: When we raise the same error message as numpy, test that


### venv/lib/python3.13/site-packages/numba/tests/test_withlifting.py

🟡 **L649** [技术债务]: is this still the cases?


### venv/lib/python3.13/site-packages/numba/tests/test_parfors.py

🟡 **L881** [技术债务]: count parfors after k-means fusion is working

🟡 **L1422** [技术债务]: this should fuse

🟡 **L1429** [技术债务]: this should also fuse


### venv/lib/python3.13/site-packages/numba/testing/notebook.py

🟡 **L81** [技术债务]: This doesn't work right now as the generated output is too diverse to


### venv/lib/python3.13/site-packages/numba/cpython/new_hashing.py

🟡 **L712** [技术债务]: this branch needs testing, needs a CPython setup for it!


### venv/lib/python3.13/site-packages/numba/cpython/old_hashing.py

🟡 **L708** [技术债务]: this branch needs testing, needs a CPython setup for it!


### venv/lib/python3.13/site-packages/numba/cpython/unicode.py

🟡 **L1853** [技术债务]: it might be possible to break here if the kind


### venv/lib/python3.13/site-packages/numba/cpython/listobj.py

🟡 **L1191** [技术债务]: To make this work, need consts as slice for start/end so as to


### venv/lib/python3.13/site-packages/numba/parfors/parfor.py

🟡 **L222** [技术债务]: investigate assert_equiv

🟡 **L233** [技术债务]: investigate assert_equiv

🟡 **L250** [技术债务]: investigate assert_equiv

🟡 **L266** [技术债务]: evaluate support for dotvm and enable

🟡 **L932** [技术债务]: trace this!

🟡 **L997** [技术债务]: do a better job of tracking parfors that are not in

🟡 **L2126** [技术债务]: add more calls

🟡 **L2536** [技术债务]: support array mask optimization for prange

🟡 **L2537** [技术债务]: refactor and simplify array mask optimization

🟡 **L3675** [技术债务]: The following assumes the target of all SetItem are outputs,

🟡 **L4421** [技术债务]: make it more accurate using ud-chains

🟡 **L4944** [技术债务]: save copies that are repeated in parfor


### venv/lib/python3.13/site-packages/numba/parfors/array_analysis.py

🟡 **L1305** [技术债务]: support cases with some but not all integer values or

🟡 **L1552** [技术债务]: getattr of npytypes.Record

🟡 **L2407** [技术债务]: handle multi-D input arrays (calc array size)

🟡 **L2900** [技术债务]: handle higher dimension cases


### venv/lib/python3.13/site-packages/numba/typed/listobject.py

🟡 **L243** [技术债务]: this needs a careful review

🟡 **L885** [技术债务]: This may be slow.  Each insert can incur a

🟡 **L921** [技术债务]: this type check works, but it isn't clear why and if it optimal


### venv/lib/python3.13/site-packages/numba/typed/dictobject.py

🟡 **L362** [技术债务]: the ptr_oldval is not used.  needed for refct

🟡 **L1074** [技术债务]: no handling of error state i.e. mutated dictionary


### venv/lib/python3.13/site-packages/numba/typed/typedobjectutils.py

🟡 **L83** [技术债务]: simplify default values; too many possible way to spell None


### venv/lib/python3.13/site-packages/numba/np/npyimpl.py

🟡 **L256** [技术债务]: check why raising a dynamic exception here fails


### venv/lib/python3.13/site-packages/numba/np/new_arraymath.py

🟡 **L1607** [技术债务]: This needs rewriting to be closer to NumPy, particularly the nan/inf


### venv/lib/python3.13/site-packages/numba/np/old_arraymath.py

🟡 **L1607** [技术债务]: This needs rewriting to be closer to NumPy, particularly the nan/inf


### venv/lib/python3.13/site-packages/numba/np/arrayobj.py

🟡 **L2386** [技术债务]: support scalar a (issue #3469)


### venv/lib/python3.13/site-packages/numba/experimental/jitclass/overloads.py

🟡 **L134** [技术债务]: use __iter__ if defined.


### venv/lib/python3.13/site-packages/numba/experimental/jitclass/base.py

🟡 **L582** [技术债务]: extract the following into a common util


### venv/lib/python3.13/site-packages/numba/core/types/functions.py

🟡 **L375** [技术债务]: With target-overload, the MethodTemplate can change depending


### venv/lib/python3.13/site-packages/numba/core/types/containers.py

🟡 **L634** [技术债务]: _sentry_forbidden_types(itemty)


### venv/lib/python3.13/site-packages/numba/core/typing/new_cmathdecl.py

🟡 **L10** [技术债务]: support non-complex arguments (floats and ints)

🟡 **L12** [技术债务]: New Type System


### venv/lib/python3.13/site-packages/numba/core/typing/old_cmathdecl.py

🟡 **L10** [技术债务]: support non-complex arguments (floats and ints)


### venv/lib/python3.13/site-packages/numba/core/typing/new_mathdecl.py

🟡 **L6** [技术债务]: New Type System


### venv/lib/python3.13/site-packages/numba/core/typing/old_builtins.py

🟡 **L280** [技术债务]: add 3 operand version


### venv/lib/python3.13/site-packages/numba/core/typing/new_builtins.py

🟡 **L275** [技术债务]: add 3 operand version


### venv/lib/python3.13/site-packages/numba/cuda/simulator/cudadrv/devicearray.py

🟡 **L205** [技术债务]: Add inplace, bitwise, unary magic methods


### venv/lib/python3.13/site-packages/numba/tests/doc_examples/test_interval_example.py

🟡 **L220** [技术债务]: This should produce a `RuntimeError`, but the `unbox` handler for `float` ignores


### venv/lib/python3.13/site-packages/numba/np/ufunc/ufuncbuilder.py

🟡 **L339** [技术债务]: handle scalar


### venv/lib/python3.13/site-packages/numba/np/ufunc/parallel.py

🟡 **L403** [技术债务]: Check that if MKL is present that it is a version


### venv/lib/python3.13/site-packages/torchgen/static_runtime/generator.py

🟡 **L81** [技术债务]: these ones got added recently and need manual inspection

🟡 **L269** [技术债务]: stop doing type tests by converting to C++ and then testing

🟡 **L295** [技术债务]: stop type testing by converting to C++


### venv/lib/python3.13/site-packages/torchgen/dest/ufunc.py

🟡 **L47** [技术债务]: use BackendIndex

🟡 **L83** [技术债务]: don't hardcode; return type will be inferred based on tags on

🟡 **L517** [技术债务]: don't hardcode ufunc:: namespace here, should be centralized smh


### venv/lib/python3.13/site-packages/torchgen/dest/lazy_ir.py

🟡 **L50** [技术债务]: Matching on CType seems wrong; should be matching on Type

🟡 **L62** [技术债务]: I don't understand when you should put lazy_ in the name

🟡 **L452** [技术债务]: (alanwaketan): Maybe we want to apply GetLtcTensorOrCreateForWrappedNumber here, but hold it

🟡 **L549** [技术债务]: this is trolling

🟡 **L590** [技术债务]: (whc) remove this if XLA switches to using static method for creation


### venv/lib/python3.13/site-packages/torchgen/dest/register_dispatch_key.py

🟡 **L447** [技术债务]: dedupe this with the structured codegen

🟡 **L475** [技术债务]: handle in place on tensor list

🟡 **L686** [技术债务]: Make sure out argument is guaranteed to be self

🟡 **L727** [技术债务]: Move to OptionalMPSGuard.

🟡 **L743** [技术债务]: audit

🟡 **L745** [技术债务]: audit

🟡 **L747** [技术债务]: audit

🟡 **L766** [技术债务]: Now, there is something interesting going on here.  In the code below,

🟡 **L842** [技术债务]: dedup this branch

🟡 **L927** [技术债务]: Stop hardcoding that the output type is a Tensor.  Note

🟡 **L942** [技术债务]: https://github.com/pytorch/pytorch/issues/53023

🟡 **L952** [技术债务]: I think this means structured won't work with method

🟡 **L981** [技术债务]: Do this in translate instead

🟡 **L999** [技术债务]: audit


### venv/lib/python3.13/site-packages/torchgen/api/translate.py

🟡 **L156** [技术债务]: My kingdom for a pattern matcher

🟡 **L159** [技术债务]: This could get us in recomputation trouble if b.expr is nontrivial.

🟡 **L260** [技术债务]: These are referentially equal, shouldn't have to do this;

🟡 **L375** [技术债务]: You might also want to solve this from longSymVec_ctype or


### venv/lib/python3.13/site-packages/torchgen/api/native.py

🟡 **L53** [技术债务]: delete this!

🟡 **L120** [技术债务]: Not sure why the arguments assigned here are for


### venv/lib/python3.13/site-packages/torchgen/api/cpp.py

🟡 **L183** [技术债务]: remove these special cases, ArrayRef fallthrough works fine

🟡 **L288** [技术债务]: Consider incorporating this into the data model

🟡 **L427** [技术债务]: this is wrong


### venv/lib/python3.13/site-packages/torchgen/api/autograd.py

🟡 **L119** [技术债务]: maybe the logic to search for all variants is no longer necessary?

🟡 **L238** [技术债务]: only to keep it byte-for-byte compatible with the old codegen, should remove.

🟡 **L246** [技术债务]: some cpp naming logic (e.g. resolving name conflict) might be irrelevant?

🟡 **L255** [技术债务]: only to keep it byte-for-byte compatible with the old codegen, should remove.

🟡 **L266** [技术债务]: Update comment below since it is out of date.

🟡 **L369** [技术债务]: (crcrpar): Avoid hard coding "Default" ideally.

🟡 **L664** [技术债务]: (crcrpar): Avoid hard coding "Default" ideally.


### venv/lib/python3.13/site-packages/torchgen/api/structured.py

🟡 **L76** [技术债务]: delete these special cases; see torchgen.api.cpp--these


### venv/lib/python3.13/site-packages/torchgen/api/python.py

🟡 **L317** [技术债务]: maybe don't need keep scattered out fields for python signature?

🟡 **L339** [技术债务]: shouldn't this be OptionalType[ListType[...]], since it defaults to None?

🟡 **L354** [技术债务]: create a dedicated SelfArgument type for 'self'?

🟡 **L371** [技术债务]: maybe create a PythonTensorOptionsArgument?

🟡 **L734** [技术债务]: directly translate a.default to python default

🟡 **L1117** [技术债务]: This is to keep same byte-for-byte result as the old codegen - maybe unnecessary?

🟡 **L1149** [技术债务]: avoid this special handling?

🟡 **L1426** [技术债务]: why this needs to be special case?

🟡 **L1496** [技术债务]: maybe move to the generator side as it's not related to binding.


### venv/lib/python3.13/site-packages/torchgen/api/lazy.py

🟡 **L126** [技术债务]: (whc) is this actually correct? or should it use a Vector like above

🟡 **L132** [技术债务]: return a value type.  The problem here is analogous to

🟡 **L147** [技术债务]: Determining this based off of CType is bad; this should be computed

🟡 **L167** [技术债务]: report True for this

🟡 **L193** [技术债务]: dedupe with Type.is_generator_like

🟡 **L210** [技术债务]: this is lies, it is false for symint list

🟡 **L232** [技术债务]: lists of symints are not currently treated as value types

🟡 **L310** [技术债务]: This is not idiomatic with how other torchgen APIs transform on schema.

🟡 **L318** [技术债务]: Need to handle collisions with argument names at some point


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/load_derivatives.py

🟡 **L185** [技术债务]: Why is this going through CppSignatureGroup, that doesn't make sense...

🟡 **L412** [技术债务]: we are trolling

🟡 **L616** [技术债务]: do we need eagerly calculate and save it here? Can it be derived

🟡 **L677** [技术债务]: maybe the logic to handle the legacy schema is no longer necessary?


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_python_functions.py

🟡 **L1266** [技术债务]: should use some canonical form instead of 'str(arg.type)' - see comments

🟡 **L1352** [技术债务]: Checking `ps.method and ('requires_grad' in parser_outputs)` is a hacky


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_autograd_functions.py

🟡 **L516** [技术债务]: This is probably not exhaustive, but it's a start


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_variable_factories.py

🟡 **L23** [技术债务]: maybe update the cpp argument API to take optional namespace argument?


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_variable_type.py

🟡 **L977** [技术债务]: it would be nice to not have these special cases

🟡 **L1128** [技术债务]: `cpp_type` is only to keep it byte-for-byte compatible with the old codegen, should remove.

🟡 **L1149** [技术债务]: (crcrpar): Make it simpler.

🟡 **L1274** [技术债务]: process all derivative formulas!!!

🟡 **L1401** [技术债务]: should be `arg.type.is_tensor_like()`?

🟡 **L1480** [技术债务]: (crcrpar): See if we can add some check e.g. `assert foreacharg is not None`.

🟡 **L1677** [技术债务]: should be str(f.func.name.name)?

🟡 **L1806** [技术债务]: flatten allocates a std::vector, which could be expensive

🟡 **L1941** [技术债务]: update this when inplace namings are unified

🟡 **L2065** [技术债务]: (crcrpar): Should this (= the foreach specific logic) be refactored somehow?


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_inplace_or_view_type.py

🟡 **L98** [技术债务]: clone indices on construction.

🟡 **L252** [技术债务]: Ideally these functions should be methods on Type class, but we have a

🟡 **L256** [技术债务]: Should handle optional here?

🟡 **L261** [技术债务]: Should handle optional here?

🟡 **L339** [技术债务]: should be str(f.func.name.name)?

🟡 **L356** [技术债务]: Clean this logic up if we get rid of reverse view funcs or reify them.


### venv/lib/python3.13/site-packages/torchgen/packaged/autograd/gen_trace_type.py

🟡 **L74** [技术债务]: figure out a better way when we support sparse tensors in jit

🟡 **L116** [技术债务]: byte-for-byte compatible with old codegen behavior - should clean up

🟡 **L307** [技术债务]: clean up old codegen behavior


### venv/lib/python3.13/site-packages/torchgen/api/types/types_base.py

🟡 **L188** [技术债务]: maybe don't represent default here


### venv/lib/python3.13/site-packages/pydantic_settings/sources/base.py

🟡 **L89** [技术债务]: we could warn if no sub command was found and one of `field_info`s


### venv/lib/python3.13/site-packages/urllib3/util/response.py

🟡 **L99** [技术债务]: Can we do this somehow without accessing private httplib _method?


### venv/lib/python3.13/site-packages/urllib3/util/url.py

🟡 **L454** [技术债务]: Remove this when we break backwards compatibility.


### venv/lib/python3.13/site-packages/urllib3/http2/__init__.py

🟡 **L38** [技术债务]: Offer 'http/1.1' as well, but for testing purposes this is handy.


### venv/lib/python3.13/site-packages/urllib3/http2/connection.py

🟡 **L144** [技术债务]: SKIPPABLE_HEADERS from urllib3 are ignored.

🟡 **L234** [技术债务]: Arbitrary read value.

🟡 **L282** [技术债务]: this is often present from upstream.

🟡 **L325** [技术债务]: This is a woefully incomplete response object, but works for non-streaming.

🟡 **L332** [技术债务]: support decoding


### venv/lib/python3.13/site-packages/setuptools/config/setupcfg.py

🟡 **L653** [技术债务]: define due date, see setuptools.dist:check_nsp.

🟡 **L772** [技术债务]: should we include due_date here? Initially introduced in 6 Aug 2022.


### venv/lib/python3.13/site-packages/setuptools/config/_apply_pyprojecttoml.py

🟡 **L528** [技术债务]: Consider removing this check in the future?


### venv/lib/python3.13/site-packages/setuptools/tests/test_egg_info.py

🟡 **L420** [技术债务]: ConfigParser does not allow : in key names!


### venv/lib/python3.13/site-packages/setuptools/tests/test_setuptools.py

🟡 **L123** [技术债务]: Evaluate if this code is needed at all.


### venv/lib/python3.13/site-packages/setuptools/tests/test_bdist_wheel.py

🟡 **L668** [技术债务]: Remove this test after deprecation period is over


### venv/lib/python3.13/site-packages/setuptools/tests/test_editable_install.py

🟡 **L1037** [技术债务]: Remove `compat` after Dec/2022.


### venv/lib/python3.13/site-packages/setuptools/command/editable_wheel.py

🟡 **L63** [技术债务]: Remove `compat` after Dec/2022.

🟡 **L84** [技术债务]: define due_date

🟡 **L291** [技术债务]: Once plugins/customizations had the chance to catch up, replace

🟡 **L324** [技术债务]: define due_date

🟡 **L591** [技术债务]: Python 3.13 replace the whole function with `bytes(content, "utf-8")`


### venv/lib/python3.13/site-packages/setuptools/command/dist_info.py

🟡 **L101** [技术债务]: if bdist_wheel if merged into setuptools, just add "keep_egg_info" there


### venv/lib/python3.13/site-packages/setuptools/command/install_lib.py

🟡 **L62** [技术债务]: is it necessary to short-circuit here? i.e. what's the cost


### venv/lib/python3.13/site-packages/setuptools/command/bdist_wheel.py

🟡 **L72** [技术债务]: armv8l, packaging pull request #690 => this did not land

🟡 **L327** [技术债务]: armv8l, packaging pull request #690 => this did not land


### venv/lib/python3.13/site-packages/setuptools/_vendor/packaging/tags.py

🟡 **L380** [技术债务]: Need to care about 32-bit PPC for ppc64 through 10.2?


### venv/lib/python3.13/site-packages/setuptools/_vendor/packaging/metadata.py

🟡 **L213** [技术债务]: The spec doesn't say anything about if the keys should be

🟡 **L883** [技术债务]: 2.1: can be in body


### venv/lib/python3.13/site-packages/setuptools/_vendor/packaging/requirements.py

🟡 **L29** [技术债务]: Can we test whether something is contained within a requirement?

🟡 **L32** [技术债务]: Can we normalize the name and extra name?


### venv/lib/python3.13/site-packages/setuptools/_vendor/wheel/_bdist_wheel.py

🟡 **L95** [技术债务]: armv8l, packaging pull request #690 => this did not land

🟡 **L347** [技术债务]: armv8l, packaging pull request #690 => this did not land


### venv/lib/python3.13/site-packages/setuptools/_vendor/autocommand/autoparse.py

🟡 **L139** [技术债务]: special case for list type.

🟡 **L152** [技术债务]: consider depluralizing metavar/name here.

🟡 **L303** [技术债务]: attach an updated __signature__ to autoparse_wrapper, just in case.


### venv/lib/python3.13/site-packages/setuptools/config/_validate_pyproject/extra_validations.py

🟡 **L97** [技术债务]: check for `include-group` cycles (can be conditional to graphlib)


### venv/lib/python3.13/site-packages/setuptools/tests/config/test_setupcfg.py

🟡 **L708** [技术债务]: investigate PyPy problem

🟡 **L729** [技术债务]: investigate PyPy problem


### venv/lib/python3.13/site-packages/setuptools/_distutils/tests/test_build_ext.py

🟡 **L87** [技术债务]: can the file be scheduled for deletion?


### venv/lib/python3.13/site-packages/greenlet/tests/test_greenlet.py

🟡 **L24** [技术债务]: Refactor into separate test files. For example,


### venv/lib/python3.13/site-packages/greenlet/tests/__init__.py

🟡 **L91** [技术债务]: We could add an API that calls us back when a particular main greenlet is deleted?


### venv/lib/python3.13/site-packages/greenlet/tests/test_leaks.py

🟡 **L248** [技术债务]: Figure out how to make this work!


### venv/lib/python3.13/site-packages/eventlet/green/threading.py

🟡 **L106** [技术债务]: move import from function body to top


### venv/lib/python3.13/site-packages/eventlet/green/zmq.py

🟡 **L189** [技术债务]: :

🟡 **L290** [技术债务]: pyzmq will copy the message buffer and create Message


### venv/lib/python3.13/site-packages/eventlet/green/MySQLdb.py

🟡 **L38** [技术债务]: support instantiating cursors.FooCursor objects directly

🟡 **L39** [技术债务]: though this is a low priority, it would be nice if we supported


### venv/lib/python3.13/site-packages/eventlet/green/ssl.py

🟡 **L472** [技术债务]: ssl.create_default_context() was added in 2.7.9.


### venv/lib/python3.13/site-packages/eventlet/greenio/py3.py

🟡 **L26** [技术债务]: get rid of this, it only seems like the original _fileobject


### venv/lib/python3.13/site-packages/eventlet/hubs/timer.py

🟡 **L79** [技术债务]: should full set be added?


### venv/lib/python3.13/site-packages/eventlet/green/urllib/request.py

🟡 **L8** [技术债务]: should we also have green email version?


### venv/lib/python3.13/site-packages/parso/python/tree.py

🟡 **L132** [技术债务]: it is really ugly that we have to override it. Maybe change


### venv/lib/python3.13/site-packages/parso/python/pep8.py

🟡 **L132** [技术债务]: unite with the code of BracketNode

🟡 **L304** [技术债务]: end_pos wrong.

🟡 **L360** [技术债务]: does this work? with brackets and stuff?

🟡 **L413** [技术债务]: is this enough checking? What about ==?

🟡 **L624** [技术债务]: should probably raise an error if there's a space here

🟡 **L664** [技术债务]: why only brackets?

🟡 **L721** [技术债务]: check multiline indentation.

🟡 **L760** [技术债务]: this is not yet ready.

🟡 **L767** [技术债务]: return self._newline_count >= 2


### venv/lib/python3.13/site-packages/parso/python/diff.py

🟡 **L440** [技术债务]: speed up, shouldn't copy the whole list all the time.

🟡 **L741** [技术债务]: this check might take a bit of time for large files. We


### venv/lib/python3.13/site-packages/parso/python/errors.py

🟡 **L676** [技术债务]: this should probably get a better end_pos including


### venv/lib/python3.13/site-packages/pydantic/v1/networks.py

🟡 **L535** [技术债务]: Needed to generic "Parts" for "Replica Set", "Sharded Cluster", and other mongodb deployment modes


### venv/lib/python3.13/site-packages/pydantic/v1/utils.py

🟡 **L270** [技术债务]: replace annotation with actual expected types once #1055 solved


### venv/lib/python3.13/site-packages/pydantic/_internal/_typing_extra.py

🟡 **L191** [技术债务]: In 2.12, delete this export. It is currently defined only to not break

🟡 **L200** [技术债务]: Ideally, we should avoid relying on the private `typing` constructs:

🟡 **L307** [技术债务]: just do getattr(obj, '__annotations__', {}) when dropping support for Python 3.9:

🟡 **L490** [技术债务]: ideally recursion errors should be checked in `eval_type` above, but `eval_type_backport`

🟡 **L626** [技术债务]: use typing.ForwardRef directly when we stop supporting 3.9:


### venv/lib/python3.13/site-packages/pydantic/_internal/_validators.py

🟡 **L45** [技术债务]: refactor sequence validation to validate with either a list or a tuple

🟡 **L135** [技术债务]: strict mode


### venv/lib/python3.13/site-packages/pydantic/_internal/_namespace_utils.py

🟡 **L236** [技术债务]: should we merge the parent namespace here?

🟡 **L263** [技术债务]: `typ.__type_params__` when we drop support for Python 3.11:


### venv/lib/python3.13/site-packages/pydantic/_internal/_repr.py

🟡 **L17** [技术债务]: remove type error comments when we drop support for Python 3.9


### venv/lib/python3.13/site-packages/pydantic/_internal/_known_annotated_metadata.py

🟡 **L84** [技术债务]: this is a bit redundant, we could probably avoid some of these


### venv/lib/python3.13/site-packages/pydantic/_internal/_generate_schema.py

🟡 **L330** [技术债务]: in theory we should check that the schema accepts a serialization key

🟡 **L434** [技术债务]: this is an ugly hack, how do we trigger an Any schema for serialization?

🟡 **L648** [技术债务]: note, this is a fairly common pattern, re lax / strict for attempted type coercion,

🟡 **L994** [技术债务]: this shouldn't be necessary (probably even this `_get_args_resolving_forward_refs()` function)

🟡 **L1676** [技术债务]: do we really need to resolve type vars here?

🟡 **L1695** [技术债务]: something like https://github.com/pydantic/pydantic/issues/5952

🟡 **L2186** [技术债务]: Should we support exclude_if from annotations?


### venv/lib/python3.13/site-packages/pydantic/_internal/_schema_gather.py

🟡 **L97** [技术债务]: When we drop 3.9, use a match statement to get better type checking and remove

🟡 **L173** [技术债务]: duplicate schema types for serializers and validators, needs to be deduplicated.

🟡 **L179** [技术债务]: duplicate schema types for serializers and validators, needs to be deduplicated.


### venv/lib/python3.13/site-packages/pydantic/_internal/_fields.py

🟡 **L45** [技术债务]: make kw_only when we drop support for 3.9.

🟡 **L47** [技术债务]: make use of PEP 747:

🟡 **L579** [技术债务]: We should probably do something with this so that validate_assignment behaves properly

🟡 **L591** [技术债务]: same note as above re validate_assignment


### venv/lib/python3.13/site-packages/pydantic/_internal/_generics.py

🟡 **L234** [技术债务]: This could be unified with `get_standard_typevars_map` if we stored the generic metadata

🟡 **L275** [技术债务]: remove parentheses when we drop support for Python 3.10:

🟡 **L314** [技术债务]: remove type ignore comment when we drop support for Python 3.9 (https://github.com/microsoft/pyright/issues/11241):


### venv/lib/python3.13/site-packages/pydantic/_internal/_utils.py

🟡 **L32** [技术债务]: remove type error comments when we drop support for Python 3.9


### venv/lib/python3.13/site-packages/pydantic/experimental/pipeline.py

🟡 **L126** [技术债务]: ultimately, make this public, see https://github.com/pydantic/pydantic/pull/9459#discussion_r1628197626

🟡 **L153** [技术债务]: use `_typing_extra.EllipsisType` when we drop Py3.9

🟡 **L158** [技术债务]: PEP 747: use TypeForm to properly type Annotated aliases (e.g. NewPath, FilePath).


### venv/lib/python3.13/site-packages/pydantic/deprecated/json.py

🟡 **L112** [技术债务]: Add a suggested migration path once there is a way to use custom encoders


### venv/lib/python3.13/site-packages/polars/series/series.py

🟡 **L1440** [技术债务]: either make a change and return py-native list data here, or find

🟡 **L1593** [技术债务]: Use variable-length strings instead when NumPy 2.0.0 comes out:

🟡 **L1612** [技术债务]: Only raise when data must be copied


### venv/lib/python3.13/site-packages/polars/series/utils.py

🟡 **L45** [技术债务]: is there a better way to do this?


### venv/lib/python3.13/site-packages/polars/_utils/udfs.py

🟡 **L152** [技术债务]: this one clashes with Python builtin abs

🟡 **L777** [技术债务]: dataframe.map... ?


### venv/lib/python3.13/site-packages/polars/dataframe/frame.py

🟡 **L1028** [技术债务]: Only raise when data must be copied

🟡 **L1168** [技术债务]: Dispatch to a native floordiv

🟡 **L1552** [技术债务]: Use python sequence constructors

🟡 **L1561** [技术债务]: we can parallelize this by calling from_numpy

🟡 **L8778** [技术债务]: Enable warning for inefficient map


### venv/lib/python3.13/site-packages/polars/datatypes/classes.py

🟡 **L840** [技术债务]: In 2.0, this should raise KeyError instead of returning if key is a str.

🟡 **L842** [技术债务]: In 2.0, this should raise TypeError instead of returning if key is None.


### venv/lib/python3.13/site-packages/polars/interchange/from_dataframe.py

🟡 **L185** [技术债务]: Cast directly to Enum


### venv/lib/python3.13/site-packages/polars/lazyframe/frame.py

🟡 **L1235** [技术债务]: drop sort once we have efficient retrieval of multiple quantiles

🟡 **L4785** [技术债务]: don't collect schema.


### venv/lib/python3.13/site-packages/polars/_utils/construction/series.py

🟡 **L201** [技术债务]: eventually go into struct builder


### venv/lib/python3.13/site-packages/polars/io/database/_cursor_proxies.py

🟡 **L47** [技术债务]: is this fetch_all not supposed to be from the argument?


### venv/lib/python3.13/site-packages/polars/io/iceberg/_utils.py

🟡 **L611** [技术债务]: Float statistics


### venv/lib/python3.13/site-packages/polars/io/csv/functions.py

🟡 **L513** [技术债务]: We can't dispatch this for all paths due to a few reasons:

🟡 **L1547** [技术债务]: This is a hack. We conditionally set `missing_columns` to mimic


### venv/lib/python3.13/site-packages/polars/io/ipc/functions.py

🟡 **L134** [技术债务]: Dispatch all paths to `scan_ipc` - this will need a breaking


### venv/lib/python3.13/site-packages/polars/testing/parametric/strategies/dtype.py

🟡 **L82** [技术债务]: Enable Object types by default when various issues are solved.

🟡 **L95** [技术债务]: Enable nested types by default when various issues are solved.


### venv/lib/python3.13/site-packages/polars/testing/parametric/strategies/data.py

🟡 **L220** [技术债务]: Enable full range of millisecond durations


### venv/lib/python3.13/site-packages/stable_baselines3/common/torch_layers.py

🟡 **L286** [技术债务]: we do not know features-dim here before going over all the items, so put something there. This is dirty!


### venv/lib/python3.13/site-packages/stable_baselines3/common/distributions.py

🟡 **L151** [技术债务]: allow action dependent std


### venv/lib/python3.13/site-packages/stable_baselines3/common/policies.py

🟡 **L613** [技术债务]: check for features_extractor


### venv/lib/python3.13/site-packages/statsmodels/robust/robust_linear_model.py

🟡 **L154** [技术债务]: then is it needed?

🟡 **L414** [技术债务]: "pvals" should come from chisq on bse?


### venv/lib/python3.13/site-packages/statsmodels/robust/norms.py

🟡 **L3** [技术债务]: add plots to weighting functions for online docs.

🟡 **L281** [技术债务]: untested, but looks right.  RamsayE not available in R or SAS?

🟡 **L492** [技术债务]: this is untested


### venv/lib/python3.13/site-packages/statsmodels/robust/scale.py

🟡 **L396** [技术债务]: raise on convergence failure?


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/kernel_regression.py

🟡 **L31** [技术债务]: make default behavior efficient=True above a certain n_obs


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/_kernel_base.py

🟡 **L94** [技术债务]: check if correct

🟡 **L230** [技术债务]: Check if 1/5 is correct in line below!

🟡 **L392** [技术债务]: remove this?


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/kernel_density.py

🟡 **L30** [技术债务]: make default behavior efficient=True above a certain n_obs


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/kde.py

🟡 **L212** [技术债务]: test for grid point at domain bound

🟡 **L277** [技术债务]: below could run into integr problems, cf. stats.dist._entropy


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/smoothers_lowess.py

🟡 **L193** [技术债务]: allow this again


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/kernels.py

🟡 **L18** [技术债务]: :

🟡 **L187** [技术债务]: why a comparison for unordered variables?


### venv/lib/python3.13/site-packages/statsmodels/tools/catadd.py

🟡 **L12** [技术债务]: this needs tests for subclasses


### venv/lib/python3.13/site-packages/statsmodels/tools/grouputils.py

🟡 **L130** [技术债务]: See if this can be entirely replaced by Grouping.dummy_sparse;

🟡 **L191** [技术债务]: use checks in combine_indices

🟡 **L195** [技术债务]: rename these to something easier to remember

🟡 **L399** [技术债务]: refactor this

🟡 **L414** [技术债务]: refactor this not to set an attribute. Why would we do this?

🟡 **L496** [技术债务]: this is not general needs to be a PanelGrouping object


### venv/lib/python3.13/site-packages/statsmodels/tools/tools.py

🟡 **L67** [技术债务]: needs to better preserve dtype and be more flexible

🟡 **L70** [技术债务]: add name validator (ie., bad names for datasets.grunfeld)

🟡 **L154** [技术债务]: add an axis argument to this for sysreg


### venv/lib/python3.13/site-packages/statsmodels/tools/rootfinding.py

🟡 **L94** [技术债务]: rtol is missing, what does it do?

🟡 **L191** [技术债务]: use Warnings, Note: brentq might still work even with max_it


### venv/lib/python3.13/site-packages/statsmodels/tools/_testing.py

🟡 **L25** [技术债务]: tt.sd and tt.tvalue are 2d also for single regressor, squeeze

🟡 **L37** [技术债务]: move this to test_attributes ?

🟡 **L44** [技术债务]: Adapt more of test_generic_methods.test_ttest_values here?

🟡 **L76** [技术债务]: Separate these out into summary/summary2 tests?


### venv/lib/python3.13/site-packages/statsmodels/tools/numdiff.py

🟡 **L16** [技术债务]: :

🟡 **L250** [技术债务]: see if this can be vectorized, but usually dim is small

🟡 **L329** [技术债务]: might want to consider lowering the step for pure derivatives


### venv/lib/python3.13/site-packages/statsmodels/tools/decorators.py

🟡 **L141** [技术债务]: Disabled since the subclasses break doc strings


### venv/lib/python3.13/site-packages/statsmodels/multivariate/pca.py

🟡 **L588** [技术债务]: This needs careful testing, with and without weights,


### venv/lib/python3.13/site-packages/statsmodels/multivariate/factor.py

🟡 **L659** [技术债务]: check row versus column convention for T


### venv/lib/python3.13/site-packages/statsmodels/discrete/discrete_model.py

🟡 **L57** [技术债务]: When we eventually get user-settable precision, we need to change

🟡 **L64** [技术债务]: add options for the parameter covariance/variance

🟡 **L241** [技术债务]: make a function factory to have multiple call-backs

🟡 **L906** [技术债务]: meaningful interpretation for `iterm`?

🟡 **L1414** [技术债务]: temporary trailing underscore to not overwrite the monkey

🟡 **L1416** [技术债务]: decide whether to move the imports

🟡 **L1425** [技术债务]: add start_params option, need access to tranformation

🟡 **L1691** [技术债务]: add full set of which

🟡 **L3220** [技术债务]: Weibull can replaced by a survival analsysis function

🟡 **L3230** [技术债务]: add analytic hessian for Weibull

🟡 **L3622** [技术债务]: replace this with analytic where is it used?

🟡 **L3719** [技术债务]: , Warning: this assumes exposure is logged

🟡 **L3765** [技术债务]: make this unnecessary ?

🟡 **L3790** [技术债务]: , Warning: this assumes exposure is logged

🟡 **L3975** [技术债务]: better name/interpretation for dgterm?

🟡 **L4537** [技术债务]: what parameters to pass to fit?

🟡 **L4539** [技术债务]: consider catching and warning on convergence failure?

🟡 **L5236** [技术债务]: nobs?

🟡 **L5243** [技术债务]: get better diagnosis


### venv/lib/python3.13/site-packages/statsmodels/discrete/discrete_margins.py

🟡 **L120** [技术债务]: handle DataFrames

🟡 **L549** [技术债务]: sigh, we really need to hold on to this in _data...

🟡 **L663** [技术债务]: if at is not all or overall, we can also put atexog values


### venv/lib/python3.13/site-packages/statsmodels/discrete/_diagnostics_count.py

🟡 **L214** [技术债务]: Warning shows up in Monte Carlo loop, skip for now

🟡 **L283** [技术债务]: use attribute, may need to be added

🟡 **L375** [技术债务]: use attribute, may need to be added


### venv/lib/python3.13/site-packages/statsmodels/discrete/diagnostic.py

🟡 **L107** [技术债务]: verify upper bound, we drop last bin (may be open, inf)

🟡 **L245** [技术债务]: what's the correct df, same as for multinomial/ordered ?


### venv/lib/python3.13/site-packages/statsmodels/discrete/count_model.py

🟡 **L265** [技术债务]: need to allow for complex to use CS numerical derivatives


### venv/lib/python3.13/site-packages/statsmodels/discrete/truncated_model.py

🟡 **L166** [技术债务]: can we rewrite to following without creating new models

🟡 **L213** [技术债务]: check how we can to this in __init__

🟡 **L1194** [技术债务]: the following should be in __init__ or initialize


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/nonlinls.py

🟡 **L199** [技术债务]: check effect of `weights` on result statistics


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/tmodel.py

🟡 **L64** [技术债务]: here or in __init__

🟡 **L111** [技术债务]: adjust scale for df

🟡 **L157** [技术债务]: check behavior around zero

🟡 **L215** [技术债务]: rename fit_mle -> fit, fit -> fit_ls


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/ordinal_model.py

🟡 **L549** [技术债务]: the following doesn't work yet because of the incremental exp

🟡 **L616** [技术债务]: add category labels


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/try_mlecov.py

🟡 **L33** [技术债务]: robust-enough check?  unneeded if _det_sigma gets defined


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/count.py

🟡 **L83** [技术债务]: why would this be ValueError instead of AttributeError?

🟡 **L84** [技术债务]: Why even make this a Model attribute in the first place?

🟡 **L174** [技术债务]: it's not standard pattern to use default exog


### venv/lib/python3.13/site-packages/statsmodels/iolib/summary.py

🟡 **L140** [技术债务]: define this generically, overwrite in model classes

🟡 **L145** [技术债务]: What happens with multiple names?

🟡 **L228** [技术债务]: exists in linear_model, what about other models

🟡 **L422** [技术债务]: check whether I do not want to refactor this

🟡 **L509** [技术债务]: check whether I do not want to refactor this

🟡 **L565** [技术债务]: note the [1:] is specific to current MNLogit

🟡 **L571** [技术债务]: check formatting options with different values

🟡 **L647** [技术债务]: this might be specific to multinomial logit type, move?

🟡 **L652** [技术债务]: note, the [1:] is specific to current MNLogit

🟡 **L700** [技术债务]: check if we have multiline headers

🟡 **L732** [技术债务]: insert \hline after updating SimpleTable


### venv/lib/python3.13/site-packages/statsmodels/iolib/tableformatting.py

🟡 **L67** [技术债务]: as of when?  compared to what?  is old version needed?

🟡 **L76** [技术债务]: need '=' at the last subtable

🟡 **L90** [技术债务]: TODO: what?


### venv/lib/python3.13/site-packages/statsmodels/iolib/table.py

🟡 **L757** [技术债务]: add checking


### venv/lib/python3.13/site-packages/statsmodels/iolib/summary2.py

🟡 **L277** [技术债务]: be more specific


### venv/lib/python3.13/site-packages/statsmodels/gam/smooth_basis.py

🟡 **L40** [技术债务]: is this copy/pasted?  If so, why do we need it?  If not, get

🟡 **L263** [技术债务]: this function should be deleted

🟡 **L288** [技术债务]: try to include other kinds of splines from patsy

🟡 **L372** [技术债务]: unclear description

🟡 **L651** [技术债务]: from CubicRegressionSplines class

🟡 **L927** [技术债务]: move attaching constraints to super call

🟡 **L1004** [技术债务]: move attaching constraints to super call

🟡 **L1020** [技术债务]: this class is still not tested

🟡 **L1032** [技术债务]: ACcording to CubicRegressionSplines class this should be


### venv/lib/python3.13/site-packages/statsmodels/gam/generalized_additive_model.py

🟡 **L23** [技术债务]: use this for pirls

🟡 **L185** [技术债务]: there might be problems is exog_smooth is 1-D

🟡 **L350** [技术债务]: resid_response does not make sense with nonlinear link

🟡 **L428** [技术债务]: does `normalized_cov_params * scale` work in all cases?

🟡 **L515** [技术债务]: check usage of hasconst

🟡 **L524** [技术债务]: handle data is experimental, see #5469

🟡 **L537** [技术债务]: alternative is to take columns from combined exog

🟡 **L551** [技术债务]: check: xnames_linear will be None instead of empty list

🟡 **L571** [技术债务]: the generic data handling might attach the design_info from the

🟡 **L621** [技术债务]: temporary hack to remove attribute

🟡 **L628** [技术债务]: alpha not allowed yet, but is in `_fit_pirls`

🟡 **L661** [技术债务]: this currently modifies several attributes

🟡 **L668** [技术债务]: we need to rescale alpha

🟡 **L675** [技术债务]: what are these values?

🟡 **L685** [技术债务]: check default scale types

🟡 **L711** [技术债务]: is this equivalent to point 1 of page 136:

🟡 **L715** [技术债务]: is this equivalent to point 1 of page 136:

🟡 **L735** [技术债务]: need atol, rtol

🟡 **L816** [技术债务]: use .copy() method when available for all types

🟡 **L935** [技术债务]: pen weight should not be defined here!!

🟡 **L961** [技术债务]: I do not understand why I need 2 * s

🟡 **L964** [技术债务]: use MinimalWLS during iterations, less overhead

🟡 **L1000** [技术债务]: needs full because of broadcasting with weights


### venv/lib/python3.13/site-packages/statsmodels/gam/gam_penalties.py

🟡 **L177** [技术债务]: Review this,


### venv/lib/python3.13/site-packages/statsmodels/sandbox/sysreg.py

🟡 **L12** [技术债务]: does it make sense of SUR equations to have

🟡 **L15** [技术债务]: make a dictionary that holds equation specific information

🟡 **L17** [技术债务]: refine sigma definition

🟡 **L91** [技术债务]: Does each equation need nobs to be the same?

🟡 **L255** [技术债务]: Should just have a general 2SLS estimator to subclass


### venv/lib/python3.13/site-packages/statsmodels/sandbox/bspline.py

🟡 **L208** [技术债务]: update parameter names, replace single character names

🟡 **L210** [技术债务]: update the use of spline order in extension code (evaluate is recursively called)

🟡 **L211** [技术债务]: eliminate duplicate M and m attributes (m is order, M is related to tau size)

🟡 **L296** [技术债务]: OWNDATA flags...


### venv/lib/python3.13/site-packages/statsmodels/sandbox/infotheo.py

🟡 **L41** [技术债务]: change these to use maxentutils so that over/underflow is handled

🟡 **L127** [技术债务]: looks okay but needs more robust tests for corner cases

🟡 **L156** [技术债务]: make this entropy, and then have different measures as

🟡 **L182** [技术债务]: have not defined the px,py case?

🟡 **L355** [技术债务]: these should be `condentropy`, not `condent`

🟡 **L390** [技术债务]: finish returns

🟡 **L391** [技术债务]: add checks for measure

🟡 **L411** [技术债务]: before completing this, need to rethink the organization of

🟡 **L493** [技术债务]: compare to pyentropy quantize?


### venv/lib/python3.13/site-packages/statsmodels/sandbox/gam.py

🟡 **L39** [技术债务]: check/catalogue required interface of a smoother

🟡 **L40** [技术债务]: replace default smoother by corresponding function to initialize

🟡 **L94** [技术债务]: change order, why copy?

🟡 **L121** [技术债务]: remove __call__

🟡 **L131** [技术债务]: what's the name in GLM

🟡 **L141** [技术债务]: transpose in smoothed and sum over axis=1

🟡 **L202** [技术债务]: why do we set here df, refactoring temporary?

🟡 **L230** [技术债务]: offset is never used ?

🟡 **L235** [技术债务]: check what smooth needs to do

🟡 **L295** [技术债务]: remove use of self.results.__call__

🟡 **L333** [技术债务]: what does GLM do? Is it actually used ?

🟡 **L349** [技术债务]: inconsistent super __init__

🟡 **L378** [技术债务]: I do not know what the next two lines do, Z, Y ? which is endog?

🟡 **L399** [技术债务]: check this

🟡 **L415** [技术债务]: code duplication with next?


### venv/lib/python3.13/site-packages/statsmodels/sandbox/descstats.py

🟡 **L169** [技术债务]: needs a by argument


### venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_estimating_equations.py

🟡 **L2003** [技术债务]: remove this method here

🟡 **L3178** [技术债务]: if at is not all or overall, we can also put atexog values


### venv/lib/python3.13/site-packages/statsmodels/genmod/qif.py

🟡 **L222** [技术债务]: Remove links.identity after deprecation final


### venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_linear_model.py

🟡 **L405** [技术债务]: check do we want to keep None as sentinel for freq_weights

🟡 **L421** [技术债务]: check do we want to keep None as sentinel for var_weights

🟡 **L830** [技术债务]: check sign, why minus?

🟡 **L1271** [技术债务]: iteration count is not always available

🟡 **L1541** [技术债务]: add start_params option, need access to tranformation

🟡 **L1600** [技术债务]: still named bse

🟡 **L1640** [技术债务]: class default

🟡 **L2163** [技术债务]: find a nicer way. gh #7840

🟡 **L2392** [技术债务]: what are these in results?


### venv/lib/python3.13/site-packages/statsmodels/treatment/treatment_effects.py

🟡 **L364** [技术债务]: need weights in outcome models

🟡 **L559** [技术债务]: make those explicit?

🟡 **L773** [技术债务]: do we keep this?


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima_process.py

🟡 **L258** [技术债务]: Should use rank 1 inverse update

🟡 **L468** [技术债务]: convert MA lag polynomial, ma_app, to be invertible, by mirroring

🟡 **L469** [技术债务]: roots outside the unit interval to ones that are inside. How to do

🟡 **L470** [技术债务]: this?

🟡 **L736** [技术债务]: Check unit root behavior

🟡 **L996** [技术债务]: variable returns like this?


### venv/lib/python3.13/site-packages/statsmodels/tsa/descriptivestats.py

🟡 **L13** [技术债务]: check subclassing for descriptive stats classes


### venv/lib/python3.13/site-packages/statsmodels/tsa/stattools.py

🟡 **L125** [技术债务]: can tcol be replaced by maxlag + 2?

🟡 **L126** [技术债务]: This could be changed to laggedRHS and exog keyword arguments if

🟡 **L165** [技术债务]: include drift keyword, only valid with regression == "c"

🟡 **L167** [技术债务]: autolag is untested

🟡 **L696** [技术债务]: should this shrink for missing="drop" and NaNs in x?

🟡 **L1191** [技术债务]: check what to return, for testing and trying out returns everything

🟡 **L1836** [技术债务]: check nobs or df = nobs - k

🟡 **L2093** [技术债务]: Remove before 0.14 is released


### venv/lib/python3.13/site-packages/statsmodels/tsa/x13.py

🟡 **L448** [技术债务]: make this more robust - give the user some control?


### venv/lib/python3.13/site-packages/statsmodels/tsa/deterministic.py

🟡 **L142** [技术债务]: Remove after pandas min ver is 1.0.0+


### venv/lib/python3.13/site-packages/statsmodels/tsa/_bds.py

🟡 **L59** [技术债务]: add functionality to select epsilon optimally

🟡 **L60** [技术债务]: and/or compute for a range of epsilons in [0.5*s, 2.0*s]?


### venv/lib/python3.13/site-packages/statsmodels/tsa/tsatools.py

🟡 **L85** [技术债务]: could be generalized for trend of aribitrary order

🟡 **L380** [技术债务]: allow list of lags additional to maxlag


### venv/lib/python3.13/site-packages/statsmodels/tsa/varma_process.py

🟡 **L373** [技术债务]: ar2s looks like a module variable, bug?


### venv/lib/python3.13/site-packages/statsmodels/tsa/adfvalues.py

🟡 **L222** [技术债务]: finish this and then integrate them into adf function


### venv/lib/python3.13/site-packages/statsmodels/tsa/ar_model.py

🟡 **L468** [技术债务]: Determine correction for degree-of-freedom

🟡 **L1151** [技术债务]: Specific to AR

🟡 **L1166** [技术债务]: Specific to AR


### venv/lib/python3.13/site-packages/statsmodels/tsa/mlemodel.py

🟡 **L24** [技术债务]: I take it this is only a stub and should be included in another


### venv/lib/python3.13/site-packages/statsmodels/regression/quantile_regression.py

🟡 **L149** [技术债务]: better start, initial beta is used only for convergence check

🟡 **L405** [技术债务]: what is recommended


### venv/lib/python3.13/site-packages/statsmodels/regression/linear_model.py

🟡 **L1** [技术债务]: Determine which tests are valid for GLSAR, and under what conditions

🟡 **L3** [技术债务]: GLS: add options Iterative GLS, for iterative fgls if sigma is None

🟡 **L4** [技术债务]: GLS: default if sigma is none should be two-step GLS

🟡 **L5** [技术债务]: Check nesting when performing model based tests, lr, wald, lm

🟡 **L532** [技术债务]: add options igls, for iterative fgls if sigma is None

🟡 **L533** [技术债务]: default if sigma is none should be two-step GLS

🟡 **L600** [技术债务]: combine this with OLS/WLS loglike and add _det_sigma argument

🟡 **L606** [技术债务]: robust-enough check? unneeded if _det_sigma gets defined

🟡 **L1275** [技术债务]: Complete docstring

🟡 **L1323** [技术债务]: update this after going through example.

🟡 **L1382** [技术债务]: notation for AR process

🟡 **L1449** [技术债务]: define R better, look back at notes and technical notes on YW.

🟡 **L1642** [技术债务]: class default

🟡 **L1648** [技术债务]: we want to get rid of 'use_t' in cov_kwds

🟡 **L1652** [技术债务]: warn or not?

🟡 **L1851** [技术债务]: What if model includes implicit constant, e.g. all

🟡 **L1853** [技术债务]: Restats as LM test by projecting orthogonalizing

🟡 **L1968** [技术债务]: make these properties reset bse

🟡 **L2225** [技术债务]: Might need demean option in S_crosssection by group?

🟡 **L2364** [技术债务]: put into separate function, needs tests

🟡 **L2471** [技术债务]: more options needed here

🟡 **L2493** [技术债务]: we need more options here

🟡 **L2526** [技术债务]: make separate function that returns a robust cov plus info

🟡 **L2546** [技术债务]: check also use_correction, do I need all combinations?

🟡 **L2554** [技术债务]: this should be outsourced in a function so we can reuse it in

🟡 **L2556** [技术债务]: make it DRYer   repeated code for checking kwargs

🟡 **L2569** [技术债务]: check if required, default in cov_hac_simple

🟡 **L2627** [技术债务]: nlags is currently required

🟡 **L2630** [技术债务]: `nlags` or `maxlags`

🟡 **L2642** [技术债务]: clumsy time index in cov_nw_panel

🟡 **L2661** [技术债务]: nlags is currently required

🟡 **L2664** [技术债务]: `nlags` or `maxlags`

🟡 **L2748** [技术债务]: Avoid adding attributes in non-__init__

🟡 **L2753** [技术债务]: not used yet

🟡 **L2757** [技术债务]: requiring list/iterable is a bit annoying

🟡 **L2759** [技术债务]: default do not work if it's not identically spelled

🟡 **L2844** [技术债务]: what is recommended?


### venv/lib/python3.13/site-packages/statsmodels/regression/mixed_linear_model.py

🟡 **L728** [技术债务]: Can this be moved up in the class hierarchy?

🟡 **L764** [技术债务]: this is wrong and should be handled upstream wholly

🟡 **L2892** [技术债务]: should use fit_kwargs


### venv/lib/python3.13/site-packages/statsmodels/regression/_prediction.py

🟡 **L105** [技术债务]: finish and cleanup

🟡 **L204** [技术债务]: check that we have correct scale, Refactor scale #???


### venv/lib/python3.13/site-packages/statsmodels/graphics/plot_grids.py

🟡 **L121** [技术债务]: make sure we have same xlim and ylim


### venv/lib/python3.13/site-packages/statsmodels/graphics/regressionplots.py

🟡 **L43** [技术债务]: consider moving to influence module

🟡 **L45** [技术债务]: replace 1 with k_constant

🟡 **L295** [技术债务]: This function does not appear to be used.

🟡 **L537** [技术债务]: maybe add option for using wendog, wexog instead

🟡 **L844** [技术债务]: how to intercept something like a margins call and adjust?

🟡 **L878** [技术债务]: what is the correct scaling and the assumption here?

🟡 **L916** [技术债务]: make configurable or let people do it ex-post?

🟡 **L1179** [技术债务]: could be a method of results

🟡 **L1180** [技术债务]: see Cook et al (1998) for a more general definition


### venv/lib/python3.13/site-packages/statsmodels/emplike/aft_el.py

🟡 **L282** [技术债务]: Vectorize, even though it is only 1 pass through for any


### venv/lib/python3.13/site-packages/statsmodels/duration/survfunc.py

🟡 **L655** [技术债务]: should use Pandas groupby


### venv/lib/python3.13/site-packages/statsmodels/duration/hazard_regression.py

🟡 **L345** [技术债务]: not used?

🟡 **L452** [技术债务]: process for missing values

🟡 **L1123** [技术债务]: some disagreements with R, not the same algorithm but


### venv/lib/python3.13/site-packages/statsmodels/distributions/edgeworth.py

🟡 **L9** [技术债务]: :

🟡 **L51** [技术债务]: higher order terms


### venv/lib/python3.13/site-packages/statsmodels/distributions/tools.py

🟡 **L324** [技术债务]: check boundary approximation, eg. undefined at zero


### venv/lib/python3.13/site-packages/statsmodels/distributions/empirical_distribution.py

🟡 **L145** [技术债务]: make `step` an arg and have a linear interpolation option?


### venv/lib/python3.13/site-packages/statsmodels/distributions/discrete.py

🟡 **L183** [技术债务]: need cdf, and rvs


### venv/lib/python3.13/site-packages/statsmodels/distributions/bernstein.py

🟡 **L77** [技术债务]: check when we have zero observations, which bin?

🟡 **L144** [技术债务]: check usage of k_grid_product. Should this go into eval?

🟡 **L210** [技术债务]: check usage of k_grid_product. Should this go into eval?

🟡 **L223** [技术债务]: check usage of k_grid_product. Should this go into eval?


### venv/lib/python3.13/site-packages/statsmodels/base/l1_cvxopt.py

🟡 **L120** [技术债务]: These retvals are returned as mle_retvals...but the fit was not ML


### venv/lib/python3.13/site-packages/statsmodels/base/_prediction_inference.py

🟡 **L151** [技术债务]: is var_resid used? drop from arguments?

🟡 **L213** [技术债务]: drop check?

🟡 **L249** [技术债务]: is var_resid used? drop from arguments?

🟡 **L340** [技术债务]: finish and cleanup

🟡 **L466** [技术债务]: check that we have correct scale, Refactor scale #???

🟡 **L526** [技术债务]: we allow endpoint transformation only for the first link

🟡 **L692** [技术债务]: currently returns NonlinearDeltaCov

🟡 **L767** [技术债务]: we allow endpoint transformation only for the first link

🟡 **L773** [技术债务]: add link or ilink to all link based models (except zi

🟡 **L832** [技术债务]: do we want covariance also, or just var/se

🟡 **L836** [技术债务]: need ci for linear prediction, method of `lin_pred


### venv/lib/python3.13/site-packages/statsmodels/base/elastic_net.py

🟡 **L178** [技术债务]: : give the user the option to switch this off


### venv/lib/python3.13/site-packages/statsmodels/base/_screening.py

🟡 **L151** [技术债务]: check what we want to do here

🟡 **L193** [技术债务]: does it really help to change/trim params

🟡 **L252** [技术债务]: remove the need for x, use x1 separately from x0

🟡 **L302** [技术债务]: we can use now np.partition with partial sort


### venv/lib/python3.13/site-packages/statsmodels/base/_penalized.py

🟡 **L40** [技术债务]: define pen_weight as average pen_weight? i.e. per observation

🟡 **L191** [技术债务]: temporary hack, need extra fit kwds

🟡 **L215** [技术债务]: make it penal function dependent

🟡 **L222** [技术债务]: do we need to add results attributes?


### venv/lib/python3.13/site-packages/statsmodels/base/covtype.py

🟡 **L150** [技术债务]: more options needed here

🟡 **L172** [技术债务]: we need more options here

🟡 **L208** [技术债务]: make separate function that returns a robust cov plus info

🟡 **L228** [技术债务]: check also use_correction, do I need all combinations?

🟡 **L236** [技术债务]: this should be outsourced in a function so we can reuse it in

🟡 **L238** [技术债务]: make it DRYer   repeated code for checking kwds

🟡 **L306** [技术债务]: nlags is currently required

🟡 **L309** [技术债务]: `nlags` or `maxlags`

🟡 **L315** [技术债务]: clumsy time index in cov_nw_panel

🟡 **L321** [技术债务]: clumsy time index in cov_nw_panel

🟡 **L337** [技术债务]: nlags is currently required

🟡 **L340** [技术债务]: `nlags` or `maxlags`


### venv/lib/python3.13/site-packages/statsmodels/base/_penalties.py

🟡 **L334** [技术债务]: `and np.size(params) > 1` is hack for llnull, need better solution

🟡 **L393** [技术债务]: weights are missing

🟡 **L450** [技术债务]: `and np.size(params) > 1` is hack for llnull, need better solution


### venv/lib/python3.13/site-packages/statsmodels/base/l1_slsqp.py

🟡 **L97** [技术债务]: These retvals are returned as mle_retvals...but the fit was not ML.


### venv/lib/python3.13/site-packages/statsmodels/base/model.py

🟡 **L187** [技术债务]: provide a docs template for args/kwargs from child models

🟡 **L188** [技术债务]: subset could use syntax. issue #469.

🟡 **L283** [技术债务]: if the intent is to re-initialize the model with new data then this

🟡 **L526** [技术债务]: separate args from nonarg taking score and hessian, ie.,

🟡 **L537** [技术债务]: why are score and hess positive?

🟡 **L599** [技术债务]: add Hessian approximation and change the above if needed

🟡 **L602** [技术债务]: hardcode scale?

🟡 **L681** [技术债务]: this could be moved into separate private method if needed

🟡 **L695** [技术债务]: do we need to change res._results.scale in some models?

🟡 **L699** [技术债务]: remove from model if not needed anymore

🟡 **L705** [技术债务]: what retvals should be required?

🟡 **L769** [技术债务]: add to results instance

🟡 **L775** [技术债务]: the below is unfinished

🟡 **L836** [技术债务]: data structures?

🟡 **L838** [技术债务]: temporary solution, force approx normal

🟡 **L1195** [技术债务]: public method?

🟡 **L1380** [技术债务]: we should not need use_t in get_robustcov_results

🟡 **L1403** [技术债务]: we should not need use_t in get_robustcov_results

🟡 **L1548** [技术债务]: make sure this works as needed for GLMs

🟡 **L1787** [技术债务]: untested for GLMs?

🟡 **L1899** [技术债务]: streamline computation, we do not need to compute J if given

🟡 **L2064** [技术债务]: maybe move DataFrame creation to results class

🟡 **L2068** [技术债务]: remove temp again, added for testing

🟡 **L2630** [技术债务]: what parameters to pass to fit?

🟡 **L2632** [技术债务]: consider catching and warning on convergence failure?

🟡 **L2723** [技术债务]: possibly move to model.fit()


### venv/lib/python3.13/site-packages/statsmodels/base/_parameter_inference.py

🟡 **L167** [技术债务]: we are computing unnecessary things for cov_type nonrobust

🟡 **L230** [技术债务]: use diag instead of full np.eye

🟡 **L262** [技术债务]: this does not work, V in fit_constrained results is singular


### venv/lib/python3.13/site-packages/statsmodels/base/optimizer.py

🟡 **L217** [技术债务]: generalize the regularization stuff

🟡 **L274** [技术债务]: code will not necessarily be general here. 3 options.


### venv/lib/python3.13/site-packages/statsmodels/base/_constraints.py

🟡 **L149** [技术债务]: make this work, there is something wrong, does not round-trip

🟡 **L330** [技术债务]: refactor to combine with above or offset_all

🟡 **L360** [技术债务]: temporary trailing underscore to not overwrite the monkey

🟡 **L362** [技术债务]: decide whether to move the imports

🟡 **L371** [技术债务]: add start_params option, need access to tranformation


### venv/lib/python3.13/site-packages/statsmodels/base/data.py

🟡 **L519** [技术债务]: remove this when we handle dtype systematically


### venv/lib/python3.13/site-packages/statsmodels/stats/descriptivestats.py

🟡 **L435** [技术债务]: Workaround for pandas AbstractMethodError in extension

🟡 **L500** [技术债务]: Remove when extension types support quantile


### venv/lib/python3.13/site-packages/statsmodels/stats/nonparametric.py

🟡 **L156** [技术债务]: use var_prob


### venv/lib/python3.13/site-packages/statsmodels/stats/stattools.py

🟡 **L68** [技术债务]: change to exception in summary branch and catch in summary()


### venv/lib/python3.13/site-packages/statsmodels/stats/oaxaca.py

🟡 **L1** [技术债务]: Non-Linear Regressions can be used

🟡 **L2** [技术债务]: Further decomposition of the two_fold parameters i.e.


### venv/lib/python3.13/site-packages/statsmodels/stats/correlation_tools.py

🟡 **L1025** [技术债务]: some other form of broadcasting may be faster than


### venv/lib/python3.13/site-packages/statsmodels/stats/oneway.py

🟡 **L169** [技术债务]: reuse general case with weights

🟡 **L782** [技术债务]: do we need a sqrt


### venv/lib/python3.13/site-packages/statsmodels/stats/moment_helpers.py

🟡 **L225** [技术债务]: no return, did it get lost in cut-paste?


### venv/lib/python3.13/site-packages/statsmodels/stats/_diagnostic_other.py

🟡 **L343** [技术债务]: Standardized to which="linear" and remove linear kwarg

🟡 **L356** [技术债务]: check for rank or redundant, note OLS calculates the rank

🟡 **L592** [技术债务]: pinv or solve ?

🟡 **L805** [技术债务]: replace with inner sandwich covariance estimator

🟡 **L951** [技术债务]: check these

🟡 **L1095** [技术债务]: not DRY, just copied from CMTNewey


### venv/lib/python3.13/site-packages/statsmodels/stats/weightstats.py

🟡 **L111** [技术债务]: why squeeze?

🟡 **L356** [技术债务]: add asymmetric

🟡 **L426** [技术债务]: check direction with R, smaller=less, larger=greater

🟡 **L429** [技术债务]: use outsourced

🟡 **L534** [技术债务]: use outsourced

🟡 **L1243** [技术债务]: remove tuple return, use same as for function tost_ind

🟡 **L1270** [技术债务]: remove tuple return, use same as for function tost_ind

🟡 **L1534** [技术债务]: this should delegate to CompareMeans like ttest_ind


### venv/lib/python3.13/site-packages/statsmodels/stats/gof.py

🟡 **L172** [技术债务]: need also binning for continuous distribution

🟡 **L237** [技术债务]: move to compatibility.py

🟡 **L391** [技术债务]: replace with TestResults


### venv/lib/python3.13/site-packages/statsmodels/stats/sandwich_covariance.py

🟡 **L315** [技术债务]: other kernels, move ?

🟡 **L470** [技术债务]: transpose return in grou_sum

🟡 **L484** [技术债务]: why transposed

🟡 **L492** [技术债务]: currently used version of groupsums requires 2d resid

🟡 **L522** [技术债务]: currently used version of groupsums requires 2d resid


### venv/lib/python3.13/site-packages/statsmodels/stats/robust_compare.py

🟡 **L119** [技术债务]: add pandas handling, maybe not if this stays internal

🟡 **L248** [技术债务]: this will not work if there is processing of meta-information


### venv/lib/python3.13/site-packages/statsmodels/stats/proportion.py

🟡 **L625** [技术债务]: refactor structure, separate norm and binom better

🟡 **L994** [技术债务]: verify that this really holds

🟡 **L996** [技术债务]: change options similar to propotion_ztost ?

🟡 **L1513** [技术债务]: odds ratio does not work if value=1

🟡 **L1759** [技术债务]: odds ratio does not work if value=1 for score test

🟡 **L1798** [技术债务]: /Note score_test_proportion_2samp returns statistic  and

🟡 **L2107** [技术债务]: avoid possible circular import, check if needed

🟡 **L2171** [技术债务]: avoid possible circular import, check if needed


### venv/lib/python3.13/site-packages/statsmodels/stats/diagnostic.py

🟡 **L220** [技术债务]: Allow cov to be specified

🟡 **L1261** [技术债务]: Remove the restriction

🟡 **L1575** [技术债务]: get critical values from Bruce Hansen's 1992 paper


### venv/lib/python3.13/site-packages/statsmodels/stats/outliers_influence.py

🟡 **L284** [技术债务]: criterion specific defaults

🟡 **L387** [技术债务]: check for extra params in e.g. NegBin

🟡 **L504** [技术债务]: use chi2   # use_f option

🟡 **L606** [技术债务]: do we cache this or does it need to be a method

🟡 **L884** [技术债务]: do I want to use different sigma estimate in

🟡 **L913** [技术债务]: do I want to use different sigma estimate in

🟡 **L990** [技术债务]: check if correct outside of ols

🟡 **L1428** [技术债务]: This will need adjustment for extra params in Poisson

🟡 **L1452** [技术债务]: we need to handle offset, exposure and weights

🟡 **L1497** [技术债务]: figure out how to do this properly


### venv/lib/python3.13/site-packages/statsmodels/stats/meta_analysis.py

🟡 **L28** [技术债务]: move to property ?

🟡 **L80** [技术债务]: maybe there is a better

🟡 **L374** [技术债务]: not used yet, design and options ?

🟡 **L460** [技术债务]: check is float_like


### venv/lib/python3.13/site-packages/statsmodels/stats/_delta_method.py

🟡 **L111** [技术债务]: why do I need to squeeze in poisson example

🟡 **L138** [技术债务]: add use_t option or not?

🟡 **L200** [技术债务]: predicted and se as arguments to avoid duplicate calculations

🟡 **L263** [技术债务]: check shape for scalar case, ContrastResults requires iterable


### venv/lib/python3.13/site-packages/statsmodels/stats/_lilliefors.py

🟡 **L212** [技术债务]: check boundaries, valid range for n and Dmax


### venv/lib/python3.13/site-packages/statsmodels/stats/power.py

🟡 **L391** [技术债务]: nobs1 and ratio are for ttest_ind,

🟡 **L432** [技术债务]: maybe use explicit kwds,

🟡 **L471** [技术债务]: I'm using the following so I get a warning when start_ttp is not defined

🟡 **L496** [技术债务]: check more cases to make this robust


### venv/lib/python3.13/site-packages/statsmodels/stats/base.py

🟡 **L97** [技术债务]: breaks with method=None


### venv/lib/python3.13/site-packages/statsmodels/stats/inter_rater.py

🟡 **L347** [技术债务]: rename to use freqs instead of probs for observed

🟡 **L400** [技术债务]: add var_kappa for weighted version


### venv/lib/python3.13/site-packages/statsmodels/stats/contrast.py

🟡 **L9** [技术债务]: should this be public if it's just a container?

🟡 **L44** [技术债务]: currently targeted to normal distribution, and chi2

🟡 **L48** [技术债务]: for results instance we decided to use tvalues also for normal

🟡 **L128** [技术债务]: should also add some extra information, e.g. robust cov ?

🟡 **L129** [技术债务]: can we infer names for constraints, xname in __init__ ?

🟡 **L149** [技术债务]: create something nicer for these casee

🟡 **L182** [技术债务]: create something nicer

🟡 **L347** [技术债务]: this is currently a minimal version, stub


### venv/lib/python3.13/site-packages/statsmodels/stats/rates.py

🟡 **L797** [技术债务]: why y2 in here and not y1, check definition of H1 "larger"

🟡 **L1018** [技术债务]: do I need these? return_results ?

🟡 **L1527** [技术债务]: avoid possible circular import, check if needed

🟡 **L1551** [技术债务]: replace or remove

🟡 **L1820** [技术债务]: avoid possible circular import, check if needed

🟡 **L1973** [技术债务]: avoid possible circular import, check if needed


### venv/lib/python3.13/site-packages/statsmodels/robust/tests/test_rlm.py

🟡 **L47** [技术债务]: get other results from SAS, though if it works for one...


### venv/lib/python3.13/site-packages/statsmodels/robust/tests/test_scale.py

🟡 **L19** [技术债务]: Can replicate these tests using stackloss data and R if this


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_kde.py

🟡 **L80** [技术债务]: nans at the boundaries

🟡 **L99** [技术债务]: nans at the boundaries

🟡 **L163** [技术债务]: enable/xfail/skip or delete

🟡 **L192** [技术债务]: nans at the boundaries

🟡 **L242** [技术债务]: nans at the boundaries

🟡 **L314** [技术债务]: in docstring but not in kernel_switch


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_kernels.py

🟡 **L30** [技术债务]: do not leave this commented-out; use or move/remove

🟡 **L71** [技术债务]: check we are using a different algorithm for se


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_lowess.py

🟡 **L78** [技术债务]: Refactor as parametrized test once nose is permanently dropped


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_kernel_regression.py

🟡 **L172** [技术债务]: add expected result


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_kernel_density.py

🟡 **L306** [技术债务]: assert missing

🟡 **L311** [技术债务]: odd numbers (?!)

🟡 **L348** [技术债务]: here we need a smaller tolerance.check!


### venv/lib/python3.13/site-packages/statsmodels/tools/tests/test_numdiff.py

🟡 **L226** [技术债务]: should be kwds

🟡 **L229** [技术债务]: I reduced precision to DEC3 from DEC4 because of

🟡 **L232** [技术债务]: should be kwds

🟡 **L236** [技术债务]: should be kwds

🟡 **L302** [技术债务]: check shape

🟡 **L338** [技术债务]: turn into tests or move/remove


### venv/lib/python3.13/site-packages/statsmodels/multivariate/tests/test_factor.py

🟡 **L223** [技术债务]: separate this and do pytest.skip?


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_discrete.py

🟡 **L107** [技术债务]: change when score_obs uses score_factor for DRYing


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_sandwich_cov.py

🟡 **L45** [技术债务]: get the test methods from regression/tests

🟡 **L141** [技术债务]: has no effect

🟡 **L166** [技术债务]: refactor xxxFit to full testing results

🟡 **L177** [技术债务]: should the default be changed?

🟡 **L179** [技术债务]: this is similar but not identical to logic in

🟡 **L187** [技术债务]: has no effect

🟡 **L264** [技术债务]: has no effect

🟡 **L294** [技术债务]: has no effect

🟡 **L317** [技术债务]: refactor xxxFit to full testing results

🟡 **L327** [技术债务]: has no effect

🟡 **L399** [技术债务]: has no effect

🟡 **L416** [技术债务]: has no effect

🟡 **L433** [技术债务]: has no effect


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_truncated_model.py

🟡 **L439** [技术债务]: two dim prediction not yet supported in frame

🟡 **L447** [技术债务]: which="var" raises AttributeError


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_constrained.py

🟡 **L151** [技术债务]: Newton fails

🟡 **L190** [技术债务]: bfgs fails

🟡 **L214** [技术债务]: bfgs fails

🟡 **L264** [技术债务]: Newton fails

🟡 **L289** [技术债务]: bfgs fails to converge. overflow somewhere?

🟡 **L314** [技术债务]: bfgs fails

🟡 **L422** [技术债务]: which chi2 are these

🟡 **L589** [技术债务]: make this into a test, or move/remove


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_count_model.py

🟡 **L162** [技术债务]: this raises with shape mismatch,

🟡 **L547** [技术债务]: check precision

🟡 **L626** [技术债务]: why does the following fail, params are not close enough to DGP


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/results/results_discrete.py

🟡 **L554** [技术债务]: is this right? not reported in stata

🟡 **L591** [技术债务]: re above Note, since the values below are *not* NaN,

🟡 **L652** [技术债务]: Should we remove the commented-out code below?

🟡 **L969** [技术债务]: Does the from Stata comment below apply to the


### venv/lib/python3.13/site-packages/statsmodels/datasets/sunspots/data.py

🟡 **L34** [技术债务]: time series


### venv/lib/python3.13/site-packages/statsmodels/datasets/nile/data.py

🟡 **L48** [技术债务]: time series


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/tests/test_poisson.py

🟡 **L31** [技术债务]: check problem with the following, precision is low,


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/tests/test_generic_mle.py

🟡 **L22** [技术债务]: needed or not

🟡 **L38** [技术债务]: design start_params needs to be an attribute,

🟡 **L246** [技术债务]: nan if exog is None,


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/tests/test_tmodel.py

🟡 **L104** [技术债务]: no resid available as attribute

🟡 **L127** [技术债务]: break into well-scoped tests

🟡 **L172** [技术债务]: no reference results yet

🟡 **L180** [技术债务]: break into well-scoped tests


### venv/lib/python3.13/site-packages/statsmodels/miscmodels/tests/test_ordinal_model.py

🟡 **L210** [技术债务]: add more properties or methods to Results class


### venv/lib/python3.13/site-packages/statsmodels/gam/tests/test_penalized.py

🟡 **L63** [技术债务]: CyclicCubicSplines raises when using pandas

🟡 **L167** [技术债务]: HC0 differs from Theil sandwich, difference is large

🟡 **L511** [技术债务]: alpha needs to be list

🟡 **L549** [技术债务]: no edf, edf corrected df_resid

🟡 **L579** [技术债务]: alpha needs to be list

🟡 **L669** [技术债务]: alpha needs to be list


### venv/lib/python3.13/site-packages/statsmodels/gam/tests/test_gam.py

🟡 **L159** [技术债务]: why do we need pen_weight=1

🟡 **L522** [技术债务]: if alpha changes in pirls this should be updated

🟡 **L608** [技术债务]: we have now alphas == alphas_glm

🟡 **L700** [技术债务]: sometimes the SE reported by partial_values is very large.

🟡 **L720** [技术债务]: alpha found by trial and error to pass assert

🟡 **L724** [技术债务]: if IRLS is used res_glm_gam has not partial_values.

🟡 **L730** [技术债务]: bug missing scale


### venv/lib/python3.13/site-packages/statsmodels/gam/gam_cross_validation/cross_validators.py

🟡 **L53** [技术债务]: X and y are redundant, we only need nobs


### venv/lib/python3.13/site-packages/statsmodels/gam/gam_cross_validation/gam_cross_validation.py

🟡 **L27** [技术债务]: cv_iterator.split only needs nobs from endog or exog

🟡 **L62** [技术债务]: Double check this part. cov_der2 is calculated with all data

🟡 **L73** [技术债务]: Double check this part. cov_der2 is calculated with all data

🟡 **L97** [技术债务]: super does not do anything with endog, exog, except get nobs

🟡 **L157** [技术债务]: add return


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/kernel_extras.py

🟡 **L31** [技术债务]: make default behavior efficient=True above a certain n_obs


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/kernels.py

🟡 **L274** [技术债务]: change the below to broadcasting when shape is sorted


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/kde2.py

🟡 **L9** [技术债务]: should this be a function?

🟡 **L21** [技术债务]: amend docs for Nd case?

🟡 **L37** [技术债务]: change attribute


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/smoothers.py

🟡 **L155** [技术债务]: check and clean this up

🟡 **L181** [技术债务]: check orientation, row or col


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tools/mctools.py

🟡 **L279** [技术债务]: autodetect or explicit option ?

🟡 **L371** [技术债务]: hardcoded 2 ?

🟡 **L380** [技术债务]: use stub instead

🟡 **L416** [技术债务]: need broadcasting in cdf

🟡 **L429** [技术债务]: use stub instead


### venv/lib/python3.13/site-packages/statsmodels/sandbox/panel/mixed.py

🟡 **L428** [技术债务]: JP added df_resid check

🟡 **L452** [技术债务]: check termination conditions, OR or AND

🟡 **L492** [技术债务]: check, change initialization to more standard pattern

🟡 **L499** [技术债务]: what todo about REML loglike, logL is not normalized

🟡 **L563** [技术债务]: just roughly, check


### venv/lib/python3.13/site-packages/statsmodels/sandbox/panel/correlation_structures.py

🟡 **L83** [技术债务]: flesh out the comment below about a bug in arma2ar

🟡 **L134** [技术债务]: dimension handling is not DRY

🟡 **L197** [技术债务]: this could move into corr_arr


### venv/lib/python3.13/site-packages/statsmodels/sandbox/panel/panelmod.py

🟡 **L128** [技术债务]: for now, we are going assume a constant, and then make the first

🟡 **L154** [技术债务]: this  structure can possibly be extracted somewhat to deal with

🟡 **L157** [技术债务]: add some dimension checks, etc.

🟡 **L171** [技术债务]: can the above be simplified to slice notation?

🟡 **L177** [技术债务]: is time always handled correctly in fromRecords?

🟡 **L179** [技术债务]: all of this might need to be refactored to explicitly rely (internally)

🟡 **L183** [技术债务]: does not conform to new initialize

🟡 **L197** [技术债务]: this could be pulled out and just have a by kwd that takes

🟡 **L199** [技术债务]: this also needs to be expanded for 'twoway'

🟡 **L216** [技术债务]: use sparse matrices

🟡 **L231** [技术债务]: Use kwd arguments or have fit_method methods?

🟡 **L319** [技术债务]: might fail with one regressor


### venv/lib/python3.13/site-packages/statsmodels/sandbox/archive/linalg_covmat.py

🟡 **L100** [技术债务]: this might be a trick todo backward instead of forward filtering

🟡 **L161** [技术债务]: wrong index in x


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tests/test_gam.py

🟡 **L179** [技术债务]: currently attached to class

🟡 **L226** [技术债务]: y_obs is twice __init__ and fit

🟡 **L315** [技术债务]: rvs generation does not work, nbinom needs 2 parameters


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tsa/diffusion.py

🟡 **L122** [技术债务]: reverse parameterization to start with final nobs and DT

🟡 **L277** [技术债务]: aggregate over time for process with observations for all t

🟡 **L280** [技术债务]: for single t, return stats.norm -> exactdist

🟡 **L306** [技术债务]: aggregate over time for process with observations for all t

🟡 **L307** [技术债务]: for single t, return stats.norm

🟡 **L363** [技术债务]: check this is still wrong, just guessing

🟡 **L382** [技术债务]: how to remove scalar array ?


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tsa/varma.py

🟡 **L31** [技术债务]: make sure VAR class returns B/params in this form.


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tsa/diffusion2.py

🟡 **L139** [技术债务]: out of bounds see top

🟡 **L220** [技术债务]: check parameterization of gamrnd, checked looks same as np

🟡 **L431** [技术债务]: x-axis


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tsa/example_arma.py

🟡 **L399** [技术债务]: plotacf was moved to graphics/tsaplots.py, and interface changed


### venv/lib/python3.13/site-packages/statsmodels/sandbox/tsa/fftarma.py

🟡 **L367** [技术债务]: check return length


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/penalized.py

🟡 **L296** [技术债务]: :

🟡 **L333** [技术债务]: is this still correct with sandwich normalized_cov_params, I guess not

🟡 **L373** [技术债务]: should we store the OLS results ?  not needed so far, but maybe cache

🟡 **L385** [技术债务]: return results class


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/gmm.py

🟡 **L156** [技术债务]: do we want to store this, might be large

🟡 **L239** [技术债务]: the following is very inefficient, solves problem (svd) twice

🟡 **L279** [技术债务]: import where we need it (for now), add as cached attributes

🟡 **L285** [技术债务]: reuse condno from somewhere else ?

🟡 **L292** [技术债务]: check what is valid.

🟡 **L299** [技术债务]: not used yet

🟡 **L303** [技术债务]: requiring list/iterable is a bit annoying

🟡 **L305** [技术债务]: default do not work if it's not identically spelled

🟡 **L314** [技术债务]: spelling

🟡 **L638** [技术债务]: add check for correct wargs keys

🟡 **L642** [技术债务]: check repeated calls to fit with different options

🟡 **L649** [技术债务]: temporary hack

🟡 **L677** [技术债务]: weights returned by fititer is inv_weights - not true anymore

🟡 **L683** [技术债务]: need to give weights options to gmmobjective_cu

🟡 **L690** [技术债务]: use Bunch instead ?

🟡 **L705** [技术债务]: remove, still keeping it temporarily

🟡 **L735** [技术债务]: should start_weights only be in `fit`

🟡 **L746** [技术债务]: add score

🟡 **L767** [技术债务]: add other optimization options and results

🟡 **L808** [技术债务]: add other optimization options and results

🟡 **L927** [技术债务]: set has_optimal_weights = True

🟡 **L977** [技术债务]: wargs are tuple or dict ?

🟡 **L988** [技术债务]: store this outside to avoid doing this inside optimization loop

🟡 **L989** [技术债务]: subclasses need to be able to add weights_methods, and remove

🟡 **L993** [技术债务]: should other weights_methods also have `ddof`

🟡 **L1034** [技术债务]: problem we do not have params in argument

🟡 **L1096** [技术债务]: approx_fprime has centered keyword

🟡 **L1120** [技术债务]: wrong superclass, I want tvalues, ... right now

🟡 **L1145** [技术债务]: add options ???)

🟡 **L1149** [技术债务]: do not do this when we want to change options

🟡 **L1193** [技术债务]: this might still be inv_weights after fititer

🟡 **L1198** [技术债务]: this is wrong, I need an estimate for omega

🟡 **L1311** [技术债务]: add a summary text for options that have been used

🟡 **L1321** [技术债务]: spelling

🟡 **L1458** [技术债务]: should start_weights only be in `fit`

🟡 **L1567** [技术债务]: move to higher class after testing

🟡 **L1571** [技术债务]: Why are ther weights in the signature - copy-paste error?

🟡 **L1665** [技术债务]: the following is very inefficient, solves problem (svd) twice

🟡 **L1693** [技术债务]: something wrong with super

🟡 **L1709** [技术债务]: vectorize this: use edf

🟡 **L1714** [技术债务]: copied from GMM, make super work

🟡 **L1723** [技术债务]: replace with or add call to distfn._fitstart

🟡 **L1795** [技术债务]: rewrite this old hack, should use fitgmm or fit maxiter=0

🟡 **L1799** [技术债务]: which weights_method?  There should not be any needed ?

🟡 **L1812** [技术债务]: should be a default


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/anova_nistcertified.py

🟡 **L58** [技术债务]: the following does not work as replacement

🟡 **L98** [技术债务]: figure out why these results are less accurate/precise


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/kernridgeregress_class.py

🟡 **L122** [技术债务]: return proper graph handles


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/treewalkerclass.py

🟡 **L322** [技术债务]: need a check/assert that this sequence is the same as the

🟡 **L375** [技术债务]: do I need this only on the lowest branches ?

🟡 **L387** [技术债务]: does this use the denominator twice now

🟡 **L405** [技术债务]: skip leaves, check this

🟡 **L407** [技术债务]: replace this with a check for branch (tuple) instead

🟡 **L411** [技术债务]: need tau possibly here

🟡 **L463** [技术债务]: where  should I add tau in the leaves


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/onewaygls.py

🟡 **L161** [技术债务]: chk sqrt


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/runmnl.py

🟡 **L69** [技术债务]: rename beta to params and include inclusive values for nested CL

🟡 **L125** [技术债务]: rename beta to params and include inclusive values for nested CL

🟡 **L326** [技术债务]: get better starting values


### venv/lib/python3.13/site-packages/statsmodels/sandbox/mcevaluate/arma.py

🟡 **L6** [技术债务]: still refactoring problem with cov_x


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/extras.py

🟡 **L432** [技术债务]: replace with super call

🟡 **L527** [技术债务]: What's this? wrong spacing, used in Transf_gen TransfTwo_gen

🟡 **L841** [技术债务]: rename these functions to have unique names


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/try_pot.py

🟡 **L39** [技术债务]: replace loop with cumsum ?

🟡 **L50** [技术债务]: without loading stats, crit = -stats.t.ppf(0.05)


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/mv_normal.py

🟡 **L329** [技术债务]: make integration limits more flexible

🟡 **L345** [技术债务]: replace this


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/otherdist.py

🟡 **L95** [技术债务]: check strange cases ? this assumes continous integers


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/estimators.py

🟡 **L228** [技术债务]: vectorize this:

🟡 **L551** [技术债务]: combine into test with binning included, check rule for number of bins


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/sppatch.py

🟡 **L86** [技术债务]: separate out this part to be used for other compact support distributions

🟡 **L145** [技术债务]: separate out this part to be used for other compact support distributions

🟡 **L296** [技术债务]: add option for Monte Carlo integration

🟡 **L425** [技术债务]: check that for a distribution with finite support the calculations are


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/transformed.py

🟡 **L45** [技术债务]: What's this? wrong spacing, used in Transf_gen TransfTwo_gen

🟡 **L384** [技术债务]: rename these functions to have unique names


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/gof_new.py

🟡 **L280** [技术债务]: split into modification and pvalue functions separately ?


### venv/lib/python3.13/site-packages/statsmodels/sandbox/stats/stats_mstats_short.py

🟡 **L160** [技术债务]: check these


### venv/lib/python3.13/site-packages/statsmodels/sandbox/stats/multicomp.py

🟡 **L890** [技术债务]: groupnobs[[i,j]] ))

🟡 **L1141** [技术债务]: test and replace with broadcasting

🟡 **L1236** [技术债务]: test and replace with broadcasting

🟡 **L1302** [技术债务]: smallest df in table

🟡 **L1776** [技术债务]: maybe convert all tuples to sets immediately, but I do not need the extra efficiency

🟡 **L1904** [技术债务]: groupnobs[[i,j]] ))


### venv/lib/python3.13/site-packages/statsmodels/sandbox/stats/contrast_tools.py

🟡 **L554** [技术债务]: several tests still missing, several are in the example with print


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/tests/test_smoothers.py

🟡 **L24** [技术债务]: check dim of coef

🟡 **L29** [技术债务]: make into attributes


### venv/lib/python3.13/site-packages/statsmodels/sandbox/panel/tests/test_random_panel.py

🟡 **L82** [技术债务]: BUG: requires call to _fit_ols


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/tests/test_gmm.py

🟡 **L57** [技术债务]: why is yg_df float32

🟡 **L95** [技术债务]: check df correction

🟡 **L118** [技术债务]: : res.bse and bse are not the same, rtol=0.09 is large in this case

🟡 **L215** [技术债务]: separate Q and J tests

🟡 **L350** [技术债务]: next two produce the same as before (looks like)

🟡 **L353** [技术债务]: does not look different

🟡 **L428** [技术债务]: next two produce the same as before (looks like)

🟡 **L431** [技术债务]: does not look different

🟡 **L623** [技术债务]: remove after testing, compare bse from 1 iteration

🟡 **L639** [技术债务]: check df correction np.sqrt(745./758 )*res1.bse matches better

🟡 **L645** [技术债务]: next two produce the same as before (looks like)

🟡 **L655** [技术债务]: resolve this

🟡 **L664** [技术债务]: ; tvalues are not available yet, no inheritance

🟡 **L690** [技术债务]: why is fvalue different, IV2SLS uses inherited linear

🟡 **L713** [技术债务]: res1.fvalue problem, see issue #1104


### venv/lib/python3.13/site-packages/statsmodels/sandbox/distributions/examples/matchdist.py

🟡 **L154** [技术债务]: calculate correct tail probability for mixture

🟡 **L227** [技术债务]: collect results and compare tail quantiles


### venv/lib/python3.13/site-packages/statsmodels/sandbox/stats/tests/test_multicomp.py

🟡 **L16** [技术债务]: testcase with 3 is not good because all pairs


### venv/lib/python3.13/site-packages/statsmodels/imputation/tests/test_bayes_mi.py

🟡 **L86** [技术债务]: why does the test tolerance need to be so slack?

🟡 **L165** [技术债务]: why does the test tolerance need to be so slack?


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/test_gee.py

🟡 **L557** [技术债务]: do not leave commented-out

🟡 **L1477** [技术债务]: pytest.mark.smoke>

🟡 **L1767** [技术债务]: pytest.mark.smoke?


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/test_glm.py

🟡 **L306** [技术债务]: no verified numbers largely SMOKE test

🟡 **L388** [技术债务]: enable or delete

🟡 **L444** [技术债务]: enable or delete

🟡 **L475** [技术债务]: enable or delete

🟡 **L557** [技术债务]: enable/xfail/skip or delete

🟡 **L558** [技术债务]: :

🟡 **L580** [技术债务]: need include logc link

🟡 **L665** [技术债务]: off by about 1, we are right with Stata

🟡 **L698** [技术债务]: enable or delete

🟡 **L712** [技术债务]: Very off from Stata?

🟡 **L725** [技术债务]: enable or delete

🟡 **L808** [技术债务]: enable or delete

🟡 **L822** [技术债务]: Big difference vs R

🟡 **L836** [技术债务]: enable or delete

🟡 **L879** [技术债务]: enable or delete

🟡 **L888** [技术债务]: enable/xfail/skip or delete

🟡 **L892** [技术债务]: enable/xfail/skip or delete

🟡 **L896** [技术债务]: enable/xfail/skip or delete

🟡 **L1242** [技术债务]: Find working examples for inverse_squared link

🟡 **L1318** [技术债务]: skip convergence failures for now

🟡 **L1355** [技术债务]: Find working examples for inverse_squared link

🟡 **L1434** [技术债务]: skip convergence failures for now

🟡 **L1521** [技术债务]: This does not work... Arrays are of different shape.

🟡 **L2164** [技术债务]: The search gets trapped in an infinite oscillation, so use


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/test_glm_weights.py

🟡 **L210** [技术债务]: find more informative reasons why these fail

🟡 **L429** [技术债务]: Find working examples for inverse_squared link

🟡 **L550** [技术债务]: skip convergence failures for now


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/test_score_test.py

🟡 **L221** [技术债务]: check why wooldrige is not very close, which pval1, pval2, pval3 ?


### venv/lib/python3.13/site-packages/statsmodels/genmod/families/varfuncs.py

🟡 **L198** [技术债务]: inherit from super


### venv/lib/python3.13/site-packages/statsmodels/genmod/families/links.py

🟡 **L721** [技术债务]: the CDFLink is untested


### venv/lib/python3.13/site-packages/statsmodels/genmod/families/family.py

🟡 **L4** [技术债务]: quasi, quasibinomial, quasipoisson

🟡 **L46** [技术债务]: change these class attributes, use valid somewhere...

🟡 **L62** [技术债务]: change the links class attribute in the families to hold

🟡 **L927** [技术债务]: it *should* work for a constant n>1 actually, if freq_weights

🟡 **L1359** [技术债务]: add the ability to use the power links with an if test


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/results/results_glm.py

🟡 **L85** [技术债务]: taken from Stata; not available in sm yet

🟡 **L1084** [技术债务]: the below will fail

🟡 **L1090** [技术债务]: if scale is analagous to Stata's dispersion, then this might be

🟡 **L1171** [技术债务]: do something with the commented-out code below

🟡 **L3862** [技术债务]: taken from Stata; not available in sm yet

🟡 **L3942** [技术债务]: taken from Stata; not available in sm yet

🟡 **L4018** [技术债务]: taken from Stata; not available in sm yet

🟡 **L4096** [技术债务]: taken from Stata; not available in sm yet

🟡 **L4184** [技术债务]: taken from Stata; not available in sm yet


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/results/gee_generate_tests.py

🟡 **L74** [技术债务]: should `e` be used somewhere?


### venv/lib/python3.13/site-packages/statsmodels/genmod/tests/results/glm_test_resids.py

🟡 **L14** [技术债务]: wrap super-long lines.  maybe put these in csv files?


### venv/lib/python3.13/site-packages/statsmodels/genmod/families/tests/test_link.py

🟡 **L27** [技术债务]: parametrize all these tess


### venv/lib/python3.13/site-packages/statsmodels/treatment/tests/test_teffects.py

🟡 **L67** [技术债务]: check ra and ipw difference 5e-6, others pass at 1e-12

🟡 **L105** [技术债务]: check ipw difference 1e-5, others pass at 1e-12

🟡 **L108** [技术债务]: check ra difference 4e-5, others pass at 1e-12


### venv/lib/python3.13/site-packages/statsmodels/tsa/filters/bk_filter.py

🟡 **L81** [技术债务]: change the docstring to ..math::?

🟡 **L82** [技术债务]: allow windowing functions to correct for Gibb's Phenomenon?


### venv/lib/python3.13/site-packages/statsmodels/tsa/filters/filtertools.py

🟡 **L142** [技术债务]: Is this correct?

🟡 **L357** [技术债务]: initialize also x for correlate


### venv/lib/python3.13/site-packages/statsmodels/tsa/filters/_utils.py

🟡 **L9** [技术债务]: allow use index labels


### venv/lib/python3.13/site-packages/statsmodels/tsa/filters/cf_filter.py

🟡 **L76** [技术债务]: cythonize/vectorize loop?, add ability for symmetric filter,


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/exponential_smoothing.py

🟡 **L162** [技术债务]: add validation for bounds (e.g. have all bounds, upper > lower)

🟡 **L163** [技术债务]: add `bounds_method` argument to choose between "usual" and


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/varmax.py

🟡 **L1067** [技术债务]: tests for:


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/sarimax.py

🟡 **L541** [技术债务]: I think the kwargs or not attached, need to recover from ???

🟡 **L715** [技术债务]: make this self._k_trend > 1 and adjust the update to take

🟡 **L1016** [技术债务]: how to set the initial variance parameters?

🟡 **L1122** [技术债务]: we may be able to revisit these states to get somewhat more

🟡 **L1124** [技术债务]: alternatively, we may be able to get better for certain models,


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tools.py

🟡 **L1859** [技术债务]: deprecate ctt?


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/initialization.py

🟡 **L709** [技术债务]: performance

🟡 **L719** [技术债务]: performance

🟡 **L740** [技术债务]: performance


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/kalman_filter.py

🟡 **L1712** [技术债务]: We should only fill in the non-masked elements of

🟡 **L2063** [技术债务]: there is a corner case here when the filter has not


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/representation.py

🟡 **L291** [技术债务]: we could technically allow k_posdef > k_states, but the Cython

🟡 **L347** [技术债务]: deprecation warning

🟡 **L355** [技术债务]: deprecation warning

🟡 **L629** [技术债务]: Need to add a check for ndim, and if the matrix has

🟡 **L665** [技术债务]: move this function to tools?

🟡 **L1048** [技术债务]: once the transition to using the Initialization objects is


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/dynamic_factor_mq.py

🟡 **L389** [技术债务]: could do more extensive validation here.

🟡 **L1341** [技术债务]: test each of these options

🟡 **L1870** [技术债务]: what about factors that only load on quarterly variables?

🟡 **L2811** [技术债务]: compute H is pretty slow


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/mlemodel.py

🟡 **L2021** [技术债务]: allow specifying measurement / state shocks for each

🟡 **L2647** [技术债务]: Case with "not approx_complex_step" is not hit in

🟡 **L2792** [技术债务]: Case with "not approx_complex_step" is not

🟡 **L3820** [技术债务]: check that the index of `comparison` matches the model

🟡 **L4066** [技术债务]: is the + 1 necessary?

🟡 **L4817** [技术债务]: catch something specific

🟡 **L4821** [技术债务]: catch something specific

🟡 **L4825** [技术债务]: catch something specific

🟡 **L5031** [技术债务]: this performs metadata wrapping, and that should be handled

🟡 **L5054** [技术债务]: finish and cleanup


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/var_model.py

🟡 **L613** [技术债务]: this code is only supporting deterministic terms as exog.

🟡 **L717** [技术债务]: currently only deterministic terms supported (exoglags==0)

🟡 **L801** [技术债务]: This expression shows up in a bunch of places, but

🟡 **L883** [技术债务]: we need to distinguish exog including trend and exog_user

🟡 **L1178** [技术债务]: use `mse` module-level function?

🟡 **L1615** [技术债务]: ------------------------------------------------------------------

🟡 **L1794** [技术债务]: see if can memoize better

🟡 **L1795** [技术债务]: much lower-hanging fruit in caching `np.trace` below.


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/vecm.py

🟡 **L405** [技术债务]: rewrite m such that a big (TxT) matrix is avoided

🟡 **L650** [技术债务]: test with a time series of 13 variables


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/irf.py

🟡 **L34** [技术债务]: , may be difficult at the moment


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/svar_model.py

🟡 **L91** [技术债务]: change this when masked support is better or with formula

🟡 **L244** [技术债务]: should give users the option to use a dof correction or not

🟡 **L270** [技术债务]: this does not look robust if A or B is None

🟡 **L341** [技术债务]: this could stand a refactor

🟡 **L355** [技术债务]: change to a warning?

🟡 **L583** [技术债务]: if you define these here, you do not also have to define


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/output.py

🟡 **L96** [技术债务]: change when we allow coef restrictions

🟡 **L102** [技术债务]: change when fit methods change

🟡 **L116** [技术债务]: do we want individual statistics or should users just


### venv/lib/python3.13/site-packages/statsmodels/tsa/regime_switching/markov_switching.py

🟡 **L507** [技术债务]: add checks for exog_tvtp consistent shape and indices

🟡 **L920** [技术债务]: add option to filter to return logged values so that we do not

🟡 **L1366** [技术债务]: catch something specific

🟡 **L1397** [技术债务]: add support for exog_tvtp_names


### venv/lib/python3.13/site-packages/statsmodels/tsa/regime_switching/markov_autoregression.py

🟡 **L417** [技术债务]: may provide unexpected results when some coefficients are not

🟡 **L447** [技术债务]: may provide unexpected results when some coefficients are not


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/model.py

🟡 **L144** [技术债务]: if trend='c', then we could alternatively use `demean=True` in

🟡 **L320** [技术债务]: may want to consider using innovations (MLE) if possible here,

🟡 **L354** [技术债务]: maybe should have standard way of computing starting


### venv/lib/python3.13/site-packages/statsmodels/tsa/ardl/model.py

🟡 **L554** [技术债务]: Missing adjustment

🟡 **L1800** [技术债务]: Check order is >= 1


### venv/lib/python3.13/site-packages/statsmodels/tsa/interp/denton.py

🟡 **L220** [技术债务]: break this out so that we can simplify the linalg?


### venv/lib/python3.13/site-packages/statsmodels/tsa/tests/test_ar.py

🟡 **L205** [技术债务]: test likelihood for ARX model?


### venv/lib/python3.13/site-packages/statsmodels/tsa/tests/test_stattools.py

🟡 **L130** [技术债务]: do not leave commented-out

🟡 **L135** [技术债务]: get test values from R?

🟡 **L235** [技术债务]: enable/xfail/skip or delete

🟡 **L253** [技术债务]: why is res1/qstat 1 short

🟡 **L304** [技术债务]: why is res1/qstat 1 short

🟡 **L308** [技术债务]: enable/xfail/skip or delete

🟡 **L567** [技术债务]: enable/xfail/skip or delete

🟡 **L1091** [技术债务]: Never used

🟡 **L1393** [技术债务]: could generalize to sigma2 != 1, if desired, after #5324 is merged


### venv/lib/python3.13/site-packages/statsmodels/tsa/holtwinters/model.py

🟡 **L1073** [技术债务]: Deprecate initial_level and related parameters from fit


### venv/lib/python3.13/site-packages/statsmodels/tsa/exponential_smoothing/base.py

🟡 **L33** [技术债务]: this was changed from the original, requires some work when

🟡 **L204** [技术债务]: check if this is reasonable for statespace

🟡 **L284** [技术债务]: changed this to nobs_effective, has to be changed when merging

🟡 **L300** [技术债务]: changed this to nobs_effective, has to be changed when merging

🟡 **L480** [技术债务]: Case with "not approx_complex_step" is not hit in

🟡 **L889** [技术债务]: catch something specific

🟡 **L893** [技术债务]: catch something specific

🟡 **L897** [技术债务]: catch something specific


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_simulate.py

🟡 **L439** [技术债务]: This is just a smoke test

🟡 **L445** [技术债务]: This is just a smoke test

🟡 **L493** [技术债务]: This is just a smoke test


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_impulse_responses.py

🟡 **L301** [技术债务]: This is just a smoke test

🟡 **L334** [技术债务]: This is just a smoke test


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_options.py

🟡 **L75** [技术债务]: test FilterResults for accurante boolean versions of options

🟡 **L224** [技术债务]: test SmootherResults for accurante boolean versions of options

🟡 **L266** [技术债务]: test changing simulation options in SimulationSmoothResults


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_exact_diffuse_filtering.py

🟡 **L571** [技术债务]: do something with this other than commenting it out?

🟡 **L797** [技术债务]: fails for the general version of forecasts_error_cov because

🟡 **L860** [技术债务]: fails

🟡 **L864** [技术债务]: KFAS disagrees for the diffuse observations for all of these

🟡 **L913** [技术债务]: KFAS disagrees for the diffuse observations for all of these

🟡 **L956** [技术债务]: do not leave this commented-out


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_representation.py

🟡 **L946** [技术债务]: just a smoke test


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_decompose.py

🟡 **L203** [技术债务]: remove this once we have the intercept contributions figured out


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_kalman.py

🟡 **L219** [技术债务]: Can we be more specific?  How can a contributor help?

🟡 **L271** [技术债务]: Can we be more specific?  How can a contributor help?


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_news.py

🟡 **L517** [技术债务]: add test for only one of the variables revising?

🟡 **L648** [技术债务]: add test for only one of the variables revising?

🟡 **L715** [技术债务]: add test for only one of the variables revising?

🟡 **L764** [技术债务]: add test for only one of the variables revising?


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/tests/test_tools.py

🟡 **L61** [技术债务]: use pytest.mark.parametrize?


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/tests/test_var_jmulti.py

🟡 **L154** [技术债务]: append more data sets for more test cases.


### venv/lib/python3.13/site-packages/statsmodels/tsa/vector_ar/tests/test_var.py

🟡 **L50** [技术债务]: not inherited, so these tests are never run!

🟡 **L120** [技术债务]: make a test?

🟡 **L128** [技术债务]: make a test?

🟡 **L843** [技术债务]: intercept differs by 4e-3, others are < 1e-12


### venv/lib/python3.13/site-packages/statsmodels/tsa/regime_switching/tests/test_markov_autoregression.py

🟡 **L803** [技术债务]: (ChadFulton): give reason for skip

🟡 **L841** [技术债务]: (ChadFulton): give reason for skip

🟡 **L845** [技术债务]: (ChadFulton): give reason for skip

🟡 **L886** [技术债务]: (ChadFulton): give reason for skip

🟡 **L890** [技术债务]: (ChadFulton): give reason for skip


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/burg.py

🟡 **L56** [技术债务]: remove when possible


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/hannan_rissanen.py

🟡 **L291** [技术债务]: Gomez and Maravall (2001) or Gomez (1998)


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/gls.py

🟡 **L131** [技术债务]: this is the approach suggested by BD (see Remark 1 in

🟡 **L192** [技术债务]: allow estimator-specific kwargs?


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/innovations.py

🟡 **L238** [技术债务]: show warning if convergence failed.


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/tests/test_innovations.py

🟡 **L129** [技术债务]: the test for sigma2 fails, but the value reported by BD (0.02117)

🟡 **L188** [技术债务]: the test for sigma2 fails; we get 2040.85 whereas BD reports


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/tests/test_yule_walker.py

🟡 **L85** [技术债务]: this does not raise an error due to the way Statsmodels'


### venv/lib/python3.13/site-packages/statsmodels/tsa/arima/estimators/tests/test_hannan_rissanen.py

🟡 **L72** [技术债务]: shouldn't allow initial_ar_order <= ar_order

🟡 **L74** [技术债务]: shouldn't allow initial_ar_order <= ma_order

🟡 **L76** [技术债务]: shouldn't allow initial_ar_order >= dataset

🟡 **L83** [技术债务]: shouldn't allow ar_order >= dataset

🟡 **L85** [技术债务]: shouldn't allow ma_order >= dataset


### venv/lib/python3.13/site-packages/statsmodels/tsa/tests/results/results_ar.py

🟡 **L87** [技术债务]: remove one of the files


### venv/lib/python3.13/site-packages/statsmodels/tsa/tests/results/results_arma.py

🟡 **L285** [技术债务]: empty array?

🟡 **L442** [技术债务]: had to change order in maroots?


### venv/lib/python3.13/site-packages/statsmodels/tsa/holtwinters/tests/test_holtwinters.py

🟡 **L357** [技术债务]: this is passing 2019-05-22 on some platforms; what has changed?

🟡 **L546** [技术债务]: this fails - different AICC definition?

🟡 **L549** [技术债务]: this fails - different BIC definition?

🟡 **L626** [技术债务]: not sure why the precision is so low here...


### venv/lib/python3.13/site-packages/statsmodels/tsa/base/tests/test_base.py

🟡 **L22** [技术债务]: Remove this, this is now valid


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_theil.py

🟡 **L74** [技术债务]: tgmixed seems to use scale from initial OLS, not from final res

🟡 **L105** [技术债务]: check again, I guess tgmixed uses final scale in hatmatrix


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_glsar_gretl.py

🟡 **L321** [技术债务]: check this, max at 2001:4

🟡 **L329** [技术债务]: not available

🟡 **L370** [技术债务]: fvalue differs from Gretl, trying any of the HCx


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_lme.py

🟡 **L29** [技术债务]: add tests with unequal group sizes

🟡 **L808** [技术债务]: better name


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_robustcov.py

🟡 **L61** [技术债务]: break into well-scoped tests

🟡 **L71** [技术债务]: confint missing

🟡 **L217** [技术债务]: confint missing

🟡 **L672** [技术债务]: low precision/agreement

🟡 **L821** [技术债务]: check standalone function


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_recursive_ls.py

🟡 **L207** [技术债务]: prediction in this case is not working.


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_regression.py

🟡 **L4** [技术债务]: Test for LM

🟡 **L224** [技术债务]: test fittedvalues and what else?

🟡 **L298** [技术债务]: need assert_close

🟡 **L670** [技术债务]: do not leave commented-out, use or move/remove

🟡 **L678** [技术债务]: Test HAC method

🟡 **L937** [技术债务]: never called

🟡 **L965** [技术债务]: never called

🟡 **L979** [技术债务]: never called

🟡 **L983** [技术债务]: do not leave this commented-out sitting here

🟡 **L984** [技术债务]: test AR

🟡 **L1037** [技术债务]: never called

🟡 **L1467** [技术债务]: params is not the same in GLS if sigma=1 / wgt, i.e 1-dim, #7755


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/results/results_quantile_regression.py

🟡 **L16** [技术债务]: why do we need lower tol?


### venv/lib/python3.13/site-packages/statsmodels/duration/tests/test_phreg.py

🟡 **L11** [技术债务]: Include some corner cases: data sets with empty strata, strata


### venv/lib/python3.13/site-packages/statsmodels/distributions/tests/test_discrete.py

🟡 **L330** [技术债务]: results method


### venv/lib/python3.13/site-packages/statsmodels/distributions/copula/archimedean.py

🟡 **L98** [技术债务]: how to we handle non-tuple args? two we allow single values?


### venv/lib/python3.13/site-packages/statsmodels/distributions/copula/extreme_value.py

🟡 **L62** [技术债务]: how to we handle non-tuple args? two we allow single values?


### venv/lib/python3.13/site-packages/statsmodels/othermod/tests/test_beta.py

🟡 **L265** [技术债务]: prec6 wrong exog if not used as keyword, no exception raised

🟡 **L291** [技术债务]: prec6 wrong exog if not used as keyword, no exception raised


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_shrink_pickle.py

🟡 **L58** [技术债务]: drop of load save is tested


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_generic_methods.py

🟡 **L197** [技术债务]: Can we choose a test case without this issue?

🟡 **L200** [技术债务]: Investigate how to resolve unseen warnings for Pyodide

🟡 **L296** [技术债务]: check if setup_class is faster than setup


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_penalized.py

🟡 **L142** [技术债务]: check, adjust cov_type

🟡 **L159** [技术债务]: check, adjust cov_type

🟡 **L193** [技术债务]: check, adjust cov_type

🟡 **L414** [技术债务]: check, adjust cov_type

🟡 **L431** [技术债务]: check, adjust cov_type

🟡 **L450** [技术债务]: check, adjust cov_type

🟡 **L469** [技术债务]: check, adjust cov_type

🟡 **L529** [技术债务]: check, adjust cov_type

🟡 **L558** [技术债务]: There are still problems with this case

🟡 **L586** [技术债务]: There are still problems with this case, see other class


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_penalties.py

🟡 **L38** [技术债务]: should ww allow this also in L@?


### venv/lib/python3.13/site-packages/statsmodels/base/tests/test_data.py

🟡 **L19** [技术债务]: do not leave commented-out, enable or move/remove

🟡 **L76** [技术债务]: see if this can be de-hacked

🟡 **L390** [技术债务]: which index do we get??

🟡 **L498** [技术债务]: be more specific about exception

🟡 **L520** [技术债务]: be more specific about exception

🟡 **L573** [技术债务]: be more specific about exception

🟡 **L597** [技术债务]: be more specific about exception


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_tost.py

🟡 **L235** [技术债务]: not used yet, some p-values are multi-testing adjusted

🟡 **L397** [技术债务]: add attributes to other cases and move to superclass


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_nonparametric.py

🟡 **L378** [技术债务]: return HolderTuple

🟡 **L380** [技术债务]: check sign/direction in lawstat

🟡 **L410** [技术债务]: return HolderTuple

🟡 **L412** [技术债务]: check sign/direction in lawstat, reversed from ours


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_weightstats.py

🟡 **L35** [技术债务]: not a test, belongs elsewhere?

🟡 **L225** [技术债务]: exception in corrcoef (scalar case)

🟡 **L555** [技术债务]: check this is this difference expected?, see test_proportion


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_gof.py

🟡 **L24** [技术债务]: no tests for ``value`` yet


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_diagnostic.py

🟡 **L169** [技术债务]: test options missing

🟡 **L225** [技术债务]: forcing the same split as R 202-90-90-1=21

🟡 **L231** [技术债务]: other options ???

🟡 **L275** [技术债务]: regressiontest, compare with Greene or Gretl or Stata

🟡 **L721** [技术债务]: breaks_hansen does not return pvalues

🟡 **L1065** [技术债务]: what's c1

🟡 **L1094** [技术债务]: finish and check thresholds and pvalues

🟡 **L1186** [技术债务]: make this a test or move/remove

🟡 **L1252** [技术债务]: what's c1, it's pvalues? -ss

🟡 **L1272** [技术债务]: finish wrapping this stuff

🟡 **L1710** [技术债务]: compare selected lags with Stata/ R to confirm

🟡 **L1721** [技术债务]: compare selected lags with Stata/ R to confirm


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_proportion.py

🟡 **L448** [技术债务]: actual alpha=0.0489  for all p_alt above

🟡 **L455** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L471** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L482** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L492** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L524** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L537** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L549** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L561** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L573** [技术债务]: I currently do not impose power>=0, i.e np.maximum(power, 0)

🟡 **L891** [技术债务]: currently regression test, need verified results


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_power.py

🟡 **L495** [技术债务]: should I switch to larger/smaller instead of "one-sided" options

🟡 **L682** [技术债务]: no class yet

🟡 **L910** [技术债务]: can something useful be made from this?


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_multivariate.py

🟡 **L200** [技术债务]: this assumes separate constraints,

🟡 **L210** [技术债务]: check return dimensions


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_moment_helpers.py

🟡 **L87** [技术债务]: mvsk2mnc not defined

🟡 **L112** [技术债务]: why did I use list as return type?


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_robust_compare.py

🟡 **L19** [技术债务]: scipy trim1 is not compatible anymore with my old unit tests


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_contrast.py

🟡 **L34** [技术债务]: this should actually test the value of the contrast, not only its dimension

🟡 **L39** [技术债务]: I do not think this should be estimable?  isestimable correct?


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_oneway.py

🟡 **L178** [技术债务]: use `data`


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_meta.py

🟡 **L53** [技术债务]: currently 1 is reference, switch labels

🟡 **L210** [技术债务]: asserts below are copy paste, DRY?


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_statstools.py

🟡 **L1** [技术债务]: Test robust skewness

🟡 **L2** [技术债务]: Test robust kurtosis


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_diagnostic_other.py

🟡 **L71** [技术债务]: a better structure ?

🟡 **L80** [技术债务]: cleanup after initial copy past

🟡 **L93** [技术债务]: Newey has different versions that all produce the same result

🟡 **L207** [技术债务]: extra return and no df in cm_test_robust Wooldridge


### venv/lib/python3.13/site-packages/statsmodels/stats/libqsturng/tests/test_qsturng.py

🟡 **L80** [技术债务]: do something with this?


### venv/lib/python3.13/site-packages/traitlets/config/configurable.py

🟡 **L250** [技术债务]: trigger change event if/when dict-update change events take place


### venv/lib/python3.13/site-packages/httpx2/_transports/base.py

🟡 **L8** [技术债务]: (Marcelo): When Python 3.10 reaches EOF, we can use `typing.Self` instead of defining those two.


### venv/lib/python3.13/site-packages/lxml/isoschematron/__init__.py

🟡 **L30** [技术债务]: Maybe lxml should provide a dedicated place for common namespace

🟡 **L31** [技术债务]: definitions?


### venv/lib/python3.13/site-packages/lxml/html/defs.py

🟡 **L1** [技术债务]: this should all be confirmed against what a DTD says


### venv/lib/python3.13/site-packages/lxml/html/__init__.py

🟡 **L55** [技术债务]: remove and clean up doctests

🟡 **L387** [技术债务]: should this check for multiple matches?

🟡 **L544** [技术债务]: while it's fine we *find* this link,

🟡 **L594** [技术债务]: this can be done in one pass with a wrapper

🟡 **L653** [技术债务]: this None test is a bit sloppy

🟡 **L764** [技术债务]: check what happens when you give html with a body, head, etc.

🟡 **L922** [技术债务]: I could do this with XPath, but would that just be

🟡 **L1103** [技术债务]: should test that it's not a relative URL or something

🟡 **L1174** [技术债务]: there should be more methods, and it's unclear if this is

🟡 **L1369** [技术债务]: should del be allowed at all?

🟡 **L1623** [技术债务]: I'm a little uncomfortable with the use of .checked


### venv/lib/python3.13/site-packages/lxml/html/formfill.py

🟡 **L79** [技术债务]: multiple="0"?

🟡 **L110** [技术债务]: but I'm not sure

🟡 **L290** [技术债务]: should this raise an exception?

🟡 **L295** [技术债务]: if error is longer than els, should it raise an error?


### venv/lib/python3.13/site-packages/scipy/linalg/_matfuncs_inv_ssq.py

🟡 **L38** [技术债务]: renovate or move this class when scipy operators are more mature

🟡 **L72** [技术债务]: renovate or move this function when SciPy operators are more mature


### venv/lib/python3.13/site-packages/scipy/linalg/_decomp.py

🟡 **L828** [技术债务]: calc optimal lwork by calling ?hbevd(lwork=-1)


### venv/lib/python3.13/site-packages/scipy/linalg/_matfuncs.py

🟡 **L201** [技术债务]: use a better error approximation


### venv/lib/python3.13/site-packages/scipy/linalg/lapack.py

🟡 **L1134** [技术债务]: unify "normalization" functions below, see gh-24505


### venv/lib/python3.13/site-packages/scipy/optimize/_linprog_rs.py

🟡 **L72** [技术债务]: test redundant row removal better

🟡 **L73** [技术债务]: make solve more efficient with BGLU? This could take a while.

🟡 **L376** [技术债务]: cythonize?


### venv/lib/python3.13/site-packages/scipy/optimize/_shgo.py

🟡 **L736** [技术债务]: Should always be self.n, this is

🟡 **L1196** [技术债务]: Only do this if global mode

🟡 **L1519** [技术债务]: Uncertain if n_prc needs to add len(self.LMC.xl_maps)


### venv/lib/python3.13/site-packages/scipy/optimize/_optimize.py

🟡 **L2050** [技术债务]: add hessp (callable or FD) to ScalarFunction?


### venv/lib/python3.13/site-packages/scipy/optimize/_linprog_util.py

🟡 **L862** [技术债务]: Fast sparse rank check?

🟡 **L876** [技术债务]: use results of first SVD in _remove_redundancy_svd


### venv/lib/python3.13/site-packages/scipy/optimize/_constraints.py

🟡 **L539** [技术债务]: when bugs in VectorFunction/LinearVectorFunction are worked out,


### venv/lib/python3.13/site-packages/scipy/optimize/_bracket.py

🟡 **L170** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/optimize/_remove_redundancy.py

🟡 **L423** [技术债务]: return these so user can eliminate from problem?


### venv/lib/python3.13/site-packages/scipy/integrate/_ode.py

🟡 **L374** [技术债务]: this really should be raise an exception. Will that break


### venv/lib/python3.13/site-packages/scipy/integrate/_tanhsinh.py

🟡 **L14** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/io/_netcdf.py

🟡 **L20** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/_lib/_array_api.py

🟡 **L1177** [技术债务]: this can return other backends e.g. tpu but they're unsupported in scipy

🟡 **L1180** [技术债务]: this can return other backends e.g. tpu but they're unsupported in scipy


### venv/lib/python3.13/site-packages/scipy/special/_lambertw.py

🟡 **L146** [技术债务]: special expert should inspect this


### venv/lib/python3.13/site-packages/scipy/differentiate/_differentiate.py

🟡 **L380** [技术债务]: (followup):

🟡 **L1101** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/sparse/_base.py

🟡 **L757** [技术债务]: sparse broadcasting


### venv/lib/python3.13/site-packages/scipy/sparse/_compressed.py

🟡 **L227** [技术债务]: check for duplicates?

🟡 **L706** [技术债务]: don't fall back to fancy indexing here

🟡 **L941** [技术债务]: explore creating a native sparsetools version of:

🟡 **L985** [技术债务]: only sort where necessary


### venv/lib/python3.13/site-packages/scipy/sparse/_bsr.py

🟡 **L134** [技术债务]: infer shape here

🟡 **L346** [技术债务]: eliminate zeros


### venv/lib/python3.13/site-packages/scipy/sparse/_index.py

🟡 **L338** [技术债务]: make sparse indexing work for sparray


### venv/lib/python3.13/site-packages/scipy/sparse/_csr.py

🟡 **L239** [技术债务]: uncomment this once it's faster:


### venv/lib/python3.13/site-packages/scipy/sparse/_matrix_io.py

🟡 **L64** [技术债务]: After a few releases, switch 2D case to save with coords only.


### venv/lib/python3.13/site-packages/scipy/sparse/_construct.py

🟡 **L176** [技术债务]: stop _sputils.validateaxis from returning `None` when len(axes)==ndim


### venv/lib/python3.13/site-packages/scipy/spatial/_kdtree.py

🟡 **L1014** [技术债务]: figure out the best dtype


### venv/lib/python3.13/site-packages/scipy/signal/_ltisys.py

🟡 **L2301** [技术债务]: This could use some more work.


### venv/lib/python3.13/site-packages/scipy/signal/_filter_design.py

🟡 **L530** [技术债务]: review threshold acc. to benchmark?

🟡 **L1658** [技术债务]: in the near future:

🟡 **L5058** [技术债务]: Make this a real public function scipy.misc.ff


### venv/lib/python3.13/site-packages/scipy/stats/_new_distributions.py

🟡 **L493** [技术债务]: add this strategy to infrastructure more generally, but allow dist


### venv/lib/python3.13/site-packages/scipy/stats/_continued_fraction.py

🟡 **L10** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/stats/_resampling.py

🟡 **L1090** [技术债务]: find a better way to do this without combining arrays


### venv/lib/python3.13/site-packages/scipy/stats/_page_trend_test.py

🟡 **L324** [技术债务]: relax this to accept 3d arrays?


### venv/lib/python3.13/site-packages/scipy/stats/_mstats_basic.py

🟡 **L2578** [技术债务]: better way to do that?


### venv/lib/python3.13/site-packages/scipy/stats/_qmc.py

🟡 **L456** [技术债务]: consider returning both the mean and the standard deviation


### venv/lib/python3.13/site-packages/scipy/stats/_discrete_distns.py

🟡 **L896** [技术债务]: Fails _cdfvec

🟡 **L1296** [技术债务]: problems sampling.


### venv/lib/python3.13/site-packages/scipy/stats/_distribution_infrastructure.py

🟡 **L45** [技术债务]: :

🟡 **L3387** [技术债务]: :

🟡 **L4437** [技术债务]: :

🟡 **L5129** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/stats/_morestats.py

🟡 **L2989** [技术债务]: calculate exact distribution considering ties


### venv/lib/python3.13/site-packages/scipy/cluster/hierarchy/_hierarchy_impl.py

🟡 **L1288** [技术债务]: ARRAY_API complex indexing not supported


### venv/lib/python3.13/site-packages/scipy/linalg/tests/test_decomp.py

🟡 **L45** [技术债务]: non-deterministic rng


### venv/lib/python3.13/site-packages/scipy/linalg/tests/test_lapack.py

🟡 **L1929** [技术债务]: Add a test for ONB?


### venv/lib/python3.13/site-packages/scipy/linalg/tests/test_blas.py

🟡 **L870** [技术债务]: narrow down to _fblas.error

🟡 **L913** [技术债务]: suppress?

🟡 **L916** [技术债务]: narrow down to _fblas.error


### venv/lib/python3.13/site-packages/scipy/optimize/tests/test_chandrupatla.py

🟡 **L964** [技术债务]: Test zero tolerance


### venv/lib/python3.13/site-packages/scipy/optimize/tests/test__remove_redundancy.py

🟡 **L5** [技术债务]: add tests for:


### venv/lib/python3.13/site-packages/scipy/optimize/tests/test_optimize.py

🟡 **L3071** [技术债务]: this test should really be equivalent to factorized version


### venv/lib/python3.13/site-packages/scipy/optimize/tests/test__dual_annealing.py

🟡 **L68** [技术债务]: there are some discontinuities in behaviour as a function of `qv`,


### venv/lib/python3.13/site-packages/scipy/optimize/tests/test__shgo.py

🟡 **L638** [技术债务]: Make default n higher for faster tests

🟡 **L772** [技术债务]: This test doesn't cover anything new, it is unknown what the


### venv/lib/python3.13/site-packages/scipy/optimize/_shgo_lib/_complex.py

🟡 **L1179** [技术债务]: Choose another det of j instead?

🟡 **L1180** [技术债务]: Unlikely to work in many cases

🟡 **L1187** [技术债务]: Note that scipy might be faster to add as an optional

🟡 **L1191** [技术债务]: Note if sign_det_A_j0 == then the point is coplanar to the

🟡 **L1217** [技术债务]: Is checking the projection of one vertex against faces of other

🟡 **L1220** [技术债务]: Literature seems to suggest using proj.T, but why is this

🟡 **L1222** [技术债务]: Replace with tolerance?


### venv/lib/python3.13/site-packages/scipy/optimize/_trustregion_constr/tr_interior_point.py

🟡 **L357** [技术债务]: Use more advanced strategies from [2]_


### venv/lib/python3.13/site-packages/scipy/optimize/_trustregion_constr/qp_subproblem.py

🟡 **L54** [技术债务]: Use a symmetric indefinite factorization


### venv/lib/python3.13/site-packages/scipy/optimize/_trustregion_constr/projections.py

🟡 **L101** [技术债务]: Use a symmetric indefinite factorization


### venv/lib/python3.13/site-packages/scipy/integrate/_rules/_gauss_legendre.py

🟡 **L56** [技术债务]: current converting to/from numpy


### venv/lib/python3.13/site-packages/scipy/integrate/_rules/_genz_malik.py

🟡 **L78** [技术债务]: Currently only support for degree 7 Genz-Malik cubature, should aim to

🟡 **L134** [技术债务]: Currently only support for the degree 5 lower rule, in the future it


### venv/lib/python3.13/site-packages/scipy/integrate/_rules/_gauss_kronrod.py

🟡 **L83** [技术债务]: nodes and weights are currently hard-coded for values 15 and 21, but in


### venv/lib/python3.13/site-packages/scipy/io/arff/_arffread.py

🟡 **L21** [技术债务]: :

🟡 **L862** [技术债务]: this is where we are spending time (~80%). I think things


### venv/lib/python3.13/site-packages/scipy/io/_harwell_boeing/hb.py

🟡 **L12** [技术债务]: :


### venv/lib/python3.13/site-packages/scipy/special/tests/test_basic.py

🟡 **L2476** [技术债务]: cannot use N itself yet; factorial uses `gamma(N+1)` resp. `(hi+lo)//2`


### venv/lib/python3.13/site-packages/scipy/special/tests/test_sf_error.py

🟡 **L34** [技术债务]: special expert should correct


### venv/lib/python3.13/site-packages/scipy/differentiate/tests/test_differentiate.py

🟡 **L596** [技术债务]: https://github.com/scipy/scipy/pull/22320#discussion_r1914898175


### venv/lib/python3.13/site-packages/scipy/_external/array_api_extra/testing.py

🟡 **L24** [技术债务]: import override from typing (requires Python >=3.12)


### venv/lib/python3.13/site-packages/scipy/_external/array_api_compat/cupy/_info.py

🟡 **L181** [技术债务]: Does this depend on device?

🟡 **L243** [技术债务]: Does this depend on device?


### venv/lib/python3.13/site-packages/scipy/_external/array_api_compat/common/_aliases.py

🟡 **L17** [技术债务]: import from typing (requires Python >=3.13)

🟡 **L310** [技术债务]: The standard is not clear about what should happen when x.ndim == 0.

🟡 **L382** [技术债务]: np.clip has other ufunc kwargs


### venv/lib/python3.13/site-packages/scipy/_external/array_api_compat/common/_helpers.py

🟡 **L42** [技术债务]: import from typing (requires Python >=3.13)

🟡 **L116** [技术债务]: Should we reject ndarray subclasses?

🟡 **L271** [技术债务]: Account for other backends.

🟡 **L300** [技术债务]: drop support for numpy<2 which didn't have __array_namespace__

🟡 **L307** [技术债务]: drop support for jax<0.4.32 which didn't have __array_namespace__

🟡 **L763** [技术债务]: Jitted JAX arrays do not have a device attribute

🟡 **L899** [技术债务]: What if our array is on the GPU already?


### venv/lib/python3.13/site-packages/scipy/_external/array_api_compat/dask/array/_aliases.py

🟡 **L64** [技术债务]: respect device keyword?

🟡 **L95** [技术债务]: respect device keyword?

🟡 **L159** [技术债务]: respect device keyword?

🟡 **L220** [技术债务]: This won't handle dask unknown shapes


### venv/lib/python3.13/site-packages/scipy/_external/array_api_compat/dask/array/linalg.py

🟡 **L23** [技术债务]: use the QR wrapper once dask

🟡 **L50** [技术债务]: can't avoid computing U or V for dask


### venv/lib/python3.13/site-packages/scipy/_external/array_api_extra/_lib/_at.py

🟡 **L23** [技术债务]: import from typing (requires Python >=3.11)


### venv/lib/python3.13/site-packages/scipy/_external/array_api_extra/_lib/_funcs.py

🟡 **L321** [技术债务]: Benchmark whether this is faster on the NumPy backend:


### venv/lib/python3.13/site-packages/scipy/_external/array_api_extra/_lib/_utils/_helpers.py

🟡 **L37** [技术债务]: import from typing (requires Python >=3.12 and >=3.13)

🟡 **L337** [技术债务]: https://github.com/pydata/sparse/issues/876

🟡 **L349** [技术债务]: https://github.com/data-apis/array-api/issues/945


### venv/lib/python3.13/site-packages/scipy/interpolate/tests/test_bsplines.py

🟡 **L645** [技术债务]: convert CubicSpline

🟡 **L661** [技术债务]: convert CubicSpline


### venv/lib/python3.13/site-packages/scipy/fft/tests/test_real_transforms.py

🟡 **L110** [技术债务]: write an array-agnostic pad


### venv/lib/python3.13/site-packages/scipy/fft/_duccfft/tests/test_basic.py

🟡 **L865** [技术债务]: Is this test actually valuable? The behavior it's testing shouldn't be


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/_interface.py

🟡 **L292** [技术债务]: determine whether user-defined `_matvec` supports batching,

🟡 **L320** [技术债务]: deprecate `np.matrix` support


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/_svdp.py

🟡 **L270** [技术债务]: once `svds` drops legacy positional `random_state` support,


### venv/lib/python3.13/site-packages/scipy/sparse/tests/test_construct.py

🟡 **L23** [技术债务]: check whether format=XXX is respected

🟡 **L1031** [技术债务]: change np.transpose to np.permute_dims when numpy 2 is min supported version

🟡 **L1043** [技术债务]: change np.transpose to np.permute_dims when numpy 2 is min supported version

🟡 **L1103** [技术债务]: change np.transpose to np.permute_dims when numpy 2 is min supported version


### venv/lib/python3.13/site-packages/scipy/sparse/tests/test_spfuncs.py

🟡 **L16** [技术债务]: expose through function


### venv/lib/python3.13/site-packages/scipy/sparse/tests/test_base.py

🟡 **L304** [技术债务]: test prune

🟡 **L305** [技术债务]: test has_sorted_indices

🟡 **L4893** [技术债务]: properly handle this assertion on ppc64le

🟡 **L5802** [技术债务]: check that NC has duplicates (which are not explicit zeros)


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/tests/test_onenormest.py

🟡 **L144** [技术债务]: this test seems to give estimates that match the table,

🟡 **L145** [技术债务]: even though no attempt has been made to deal with

🟡 **L146** [技术债务]: complex numbers in the one-norm estimation.


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/tests/test_interface.py

🟡 **L1146** [技术债务]: ideas:


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/_isolve/minres.py

🟡 **L364** [技术债务]: check this


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/_eigen/tests/test_svds.py

🟡 **L634** [技术债务]: arpack crashes when v0=v0, which="SM"


### venv/lib/python3.13/site-packages/scipy/sparse/linalg/_isolve/tests/test_iterative.py

🟡 **L29** [技术债务]: check that method preserve shape and type

🟡 **L30** [技术债务]: test both preconditioner methods

🟡 **L96** [技术债务]: pydata/sparse for sparse tests?

🟡 **L447** [技术债务]: minres / tfqmr. It didn't historically use absolute tolerances, so


### venv/lib/python3.13/site-packages/scipy/spatial/transform/_rotation_xp.py

🟡 **L614** [技术债务]: Can we somehow avoid this?

🟡 **L643** [技术债务]: Replace with .mT once numpy 2.0 is the minimum supported version

🟡 **L772** [技术债务]: We currently need to always compute the sensitivity matrix because lazy code

🟡 **L846** [技术债务]: Array API does not support fancy indexing __setitem__. The code is


### venv/lib/python3.13/site-packages/scipy/spatial/transform/_rotation.py

🟡 **L2220** [技术债务]: This special case handling is mainly a result of Array API limitations.

🟡 **L2284** [技术债务]: We should move to one single way of specifying the output shape and

🟡 **L2352** [技术债务]: We should move to one single way of specifying the output shape and


### venv/lib/python3.13/site-packages/scipy/spatial/transform/tests/test_rotation.py

🟡 **L2575** [技术债务]: Do we want to support this for all Array API frameworks?


### venv/lib/python3.13/site-packages/scipy/signal/tests/test_signaltools.py

🟡 **L3157** [技术债务]: . Look into making tests using this work for CuPy.


### venv/lib/python3.13/site-packages/scipy/signal/tests/test_bsplines.py

🟡 **L114** [技术债务]: for complex types, the computations are done in


### venv/lib/python3.13/site-packages/scipy/signal/tests/test_ltisys.py

🟡 **L605** [技术债务]: add meaningful test where X0 is a list

🟡 **L677** [技术债务]: add meaningful test where X0 is a list


### venv/lib/python3.13/site-packages/scipy/signal/tests/test_filter_design.py

🟡 **L1184** [技术债务]: split into multiple tests, or parameterize across filter types

🟡 **L2761** [技术债务]: Why so inaccurate?  Is reference flawed?

🟡 **L2766** [技术债务]: Why so inaccurate?  Is reference flawed?

🟡 **L2776** [技术债务]: Why so inaccurate?  Is reference flawed?

🟡 **L2781** [技术债务]: Why so inaccurate?  Is reference flawed?


### venv/lib/python3.13/site-packages/scipy/stats/_levy_stable/__init__.py

🟡 **L193** [技术债务]: add more where possible with test coverage,

🟡 **L328** [技术债务]: add more where possible with test coverage,


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_mstats_basic.py

🟡 **L1325** [技术债务]: for all ttest functions, add tests with masked array inputs


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_continuous.py

🟡 **L905** [技术债务]: add `supported` method and check here


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_stats.py

🟡 **L79** [技术债务]: write these tests to handle missing values properly

🟡 **L6251** [技术债务]: isolate use of alt backend to ttest_ind


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_continuous_basic.py

🟡 **L139** [技术债务]: multiple checks in this function are not robust, tweaking the


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_fast_gen_inversion.py

🟡 **L144** [技术债务]: add more distributions


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_marray.py

🟡 **L357** [技术债务]: add 'wilcox', 'pratt'

🟡 **L360** [技术债务]: add 'exact', 'auto'

🟡 **L376** [技术债务]: add 'exact', 'auto'

🟡 **L410** [技术债务]: add methods


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_hypotests.py

🟡 **L31** [技术债务]: complete input validation tests


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_resampling.py

🟡 **L1545** [技术债务]: change to jax_jit=False

🟡 **L1554** [技术债务]: use `xp` as backend when `ks_2samp` supports more backends

🟡 **L1569** [技术债务]: change to jax_jit=False

🟡 **L1583** [技术债务]: use `xp` as backend when `ansari` is translated to array API

🟡 **L1677** [技术债务]: change to jax_jit=False

🟡 **L1687** [技术债务]: use `xp` as backend when `wilcoxon` is translated to array API

🟡 **L1695** [技术债务]: use `xp` as backend when `wilcoxon` is translated to array API

🟡 **L1740** [技术债务]: change to jax_jit=False

🟡 **L1748** [技术债务]: use `xp` as backend when `kendalltau` is translated to array API

🟡 **L1842** [技术债务]: change to jax_jit=False

🟡 **L1882** [技术债务]: use `xp` as backend when `ansari` is translated to array API

🟡 **L1919** [技术债务]: change to jax_jit=False

🟡 **L1945** [技术债务]: use `xp` as backend when cupy works with `rankdata`


### venv/lib/python3.13/site-packages/gitdb/test/test_pack.py

🟡 **L247** [技术债务]: hex-edit a pack helping us to verify that we can handle 64 byte offsets


### venv/lib/python3.13/site-packages/git/objects/commit.py

🟡 **L602** [技术债务]: Review this - it seems process handling got a bit out of control due to


### venv/lib/python3.13/site-packages/git/index/typ.py

🟡 **L64** [技术债务]: Change to use `PosixPath.is_relative_to` once Python 3.8 is no


### venv/lib/python3.13/site-packages/git/index/base.py

🟡 **L196** [技术债务]: Look into whether we can just remove this except clause now.

🟡 **L782** [技术债务]: variable undefined

🟡 **L1405** [技术债务]: Reading from GIL!


### venv/lib/python3.13/site-packages/git/repo/base.py

🟡 **L398** [技术债务]: Find these references and ensure they are closed and deleted


### venv/lib/python3.13/site-packages/git/objects/submodule/base.py

🟡 **L1193** [技术债务]: If we run into permission problems, we have a highly


### venv/lib/python3.13/site-packages/pandas/core/nanops.py

🟡 **L128** [技术债务]: (GH-18976) update all the nanops methods to


### venv/lib/python3.13/site-packages/pandas/core/algorithms.py

🟡 **L155** [技术债务]: no test cases get here

🟡 **L492** [技术债务]: Share with _find_common_type_compat

🟡 **L513** [技术债务]: not quite right ... Sparse/Categorical

🟡 **L1411** [技术债务]: require axis == 0


### venv/lib/python3.13/site-packages/pandas/core/resample.py

🟡 **L448** [技术债务]: test_resample_apply_with_additional_args fails if we go

🟡 **L2819** [技术债务]: should we disallow non-DatetimeIndex?


### venv/lib/python3.13/site-packages/pandas/core/arraylike.py

🟡 **L361** [技术债务]: When we support multiple values in __finalize__, this

🟡 **L516** [技术债务]: test cases where this doesn't hold, i.e. 2D DTA/TDA


### venv/lib/python3.13/site-packages/pandas/core/construction.py

🟡 **L795** [技术债务]: test cases with arr.dtype.kind in "mM"


### venv/lib/python3.13/site-packages/pandas/core/config_init.py

🟡 **L426** [技术债务]: (3.0): enforcing this deprecation will close GH#52501

🟡 **L468** [技术债务]: better name?

🟡 **L517** [技术债务]: we can remove extra message after 3.0


### venv/lib/python3.13/site-packages/pandas/core/generic.py

🟡 **L5590** [技术债务]: Decide if we care about having different examples for different

🟡 **L5707** [技术债务]: speed up on homogeneous DataFrame objects (see _reindex_multi)

🟡 **L6651** [技术债务]: (EA2D): special case not needed with 2D EAs

🟡 **L8010** [技术债务]: get this to show up as the default in the docs?

🟡 **L8019** [技术债务]: Consider copy-on-write for non-replaced columns's here

🟡 **L8507** [技术债务]: (3.0): remove this case

🟡 **L8508** [技术债务]: warn/raise on limit_direction or kwargs which are ignored?

🟡 **L10431** [技术债务]: (3.0): enforcing this deprecation will close GH#13194

🟡 **L10769** [技术债务]: (EA2D): avoid object-dtype cast in EA case GH#38729

🟡 **L12263** [技术债务]: (EA2D): special-case not needed


### venv/lib/python3.13/site-packages/pandas/core/series.py

🟡 **L2274** [技术债务]: integrate bottleneck

🟡 **L2340** [技术债务]: Add option for bins like value_counts()

🟡 **L4152** [技术债务]: (3.0): once this deprecation is enforced we can call

🟡 **L6158** [技术债务]: Different from DataFrame._align_for_op, list, tuple and ndarray

🟡 **L6249** [技术债务]: result should always be ArrayLike, but this fails for some


### venv/lib/python3.13/site-packages/pandas/core/common.py

🟡 **L342** [技术债务]: used only once in indexing; belongs elsewhere?


### venv/lib/python3.13/site-packages/pandas/core/frame.py

🟡 **L900** [技术债务]: (EA2D): special case not needed with 2D EAs

🟡 **L1112** [技术债务]: (EA2D) special case would be unnecessary with 2D EAs

🟡 **L1908** [技术债务]: speed up Series case

🟡 **L3391** [技术债务]: a generic formatter wld b in DataFrameFormatter

🟡 **L5295** [技术债务]: Remove kludge in sanitize_array for string mode when enforcing

🟡 **L5941** [技术债务]: (EA2D): doing this in a loop unnecessary with 2D EAs

🟡 **L7973** [技术债务]: The previous assertion `assert right._indexed_same(self)`

🟡 **L7977** [技术债务]: operate_blockwise expects a manager of the same type

🟡 **L8092** [技术债务]: any other cases we should handle here?

🟡 **L8101** [技术债务]: is there a shortcut available when len(cols) == 0?

🟡 **L8251** [技术债务]: (EA2D): no need to special-case with 2D EAs

🟡 **L8281** [技术债务]: We could allow this in cases where we end up going

🟡 **L9021** [技术债务]: Support other joins

🟡 **L10100** [技术债务]: _shallow_copy(subset)?


### venv/lib/python3.13/site-packages/pandas/core/indexing.py

🟡 **L950** [技术债务]: this assumes only one Ellipsis

🟡 **L954** [技术债务]: other cases?  only one test gets here, and that is covered

🟡 **L1885** [技术债务]: GH#42099#issuecomment-864326014

🟡 **L1901** [技术债务]: re-issue this with setitem-specific message?

🟡 **L1981** [技术债务]: avoid np.ndim call in case it isn't an ndarray, since

🟡 **L2187** [技术债务]: (EA): ExtensionBlock.setitem this causes issues with

🟡 **L2233** [技术债务]: re-issue this with setitem-specific message?


### venv/lib/python3.13/site-packages/pandas/core/base.py

🟡 **L227** [技术债务]: following GH#45287 can we now use .drop directly without


### venv/lib/python3.13/site-packages/pandas/core/apply.py

🟡 **L922** [技术债务]: Avoid having to change state

🟡 **L1027** [技术债务]: mixed type case

🟡 **L1125** [技术债务]: GH#39993 - Avoid special-casing by replacing with lambda

🟡 **L1257** [技术债务]: (EA2D): special case would be unnecessary with 2D EAs

🟡 **L1296** [技术债务]: values corrupted without the copy

🟡 **L1499** [技术债务]: remove the `na_action="ignore"` when that default has been changed in

🟡 **L1767** [技术债务]: aggspec type: typing.Dict[str, List[AggScalar]]

🟡 **L1914** [技术债务]: Can't use, because mypy doesn't like us setting __name__


### venv/lib/python3.13/site-packages/pandas/io/pytables.py

🟡 **L2490** [技术债务]: (EA2D): not necessary with 2D EAs

🟡 **L2677** [技术债务]: should the message here be more specifically non-str?

🟡 **L3162** [技术债务]: we only have a few tests that get here, the only EA

🟡 **L3385** [技术债务]: (ArrayManager) HDFStore relies on accessing the blocks

🟡 **L3759** [技术债务]: why kind_attr here?

🟡 **L3767** [技术债务]: figure out why these two versions of `meta` dont always match.

🟡 **L4006** [技术债务]: do we always have validate=True here?

🟡 **L4104** [技术债务]: should the message here be more specifically non-str?

🟡 **L4186** [技术债务]: get this into constructor, only for appropriate subclass

🟡 **L4206** [技术债务]: (ArrayManager) HDFStore relies on accessing the blocks

🟡 **L4219** [技术债务]: prove that we only get here with axis == 1?

🟡 **L4900** [技术债务]: can we get a typ for this?  AFAICT it is the only place

🟡 **L5408** [技术债务]: we used to reshape for the dt64tz case, but no longer


### venv/lib/python3.13/site-packages/pandas/io/common.py

🟡 **L373** [技术债务]: fsspec can also handle HTTP via requests, but leaving this


### venv/lib/python3.13/site-packages/pandas/io/sql.py

🟡 **L120** [技术债务]: not reached 2023-10-27; needed?

🟡 **L182** [技术债务]: Arrow still infers strings arrays as regular strings instead

🟡 **L933** [技术债务]: support for multiIndex

🟡 **L1434** [技术债务]: Refine integer size.


### venv/lib/python3.13/site-packages/pandas/io/stata.py

🟡 **L339** [技术债务]: (non-nano): If/when pandas supports more than datetime64[ns], this

🟡 **L608** [技术债务]: could avoid converting string dtype to object here,

🟡 **L1966** [技术债务]: if we get a non-copying rename_categories, use that

🟡 **L1985** [技术债务]: is the next line needed above in the data(...) method?

🟡 **L2189** [技术债务]: expand to handle datetime to integer conversion

🟡 **L2226** [技术债务]: Refactor to combine type with format

🟡 **L2227** [技术债务]: expand this to handle a default datetime format?

🟡 **L2678** [技术债务]: could also handle string dtype here specifically

🟡 **L2994** [技术债务]: expand to handle datetime to integer conversion


### venv/lib/python3.13/site-packages/pandas/tests/test_downstream.py

🟡 **L310** [技术债务]: could check with arraylike of Period objects


### venv/lib/python3.13/site-packages/pandas/tests/test_multilevel.py

🟡 **L161** [技术债务]: groupby with level_values drops names


### venv/lib/python3.13/site-packages/pandas/_testing/__init__.py

🟡 **L226** [技术债务]: Add container like pyarrow types:


### venv/lib/python3.13/site-packages/pandas/_testing/asserters.py

🟡 **L599** [技术债务]: (infer_string) this special case could be avoided if we have


### venv/lib/python3.13/site-packages/pandas/_testing/contexts.py

🟡 **L228** [技术债务]: update match


### venv/lib/python3.13/site-packages/pandas/core/reshape/tile.py

🟡 **L503** [技术债务]: handle mismatch between categorical label order and pandas.cut order.


### venv/lib/python3.13/site-packages/pandas/core/reshape/merge.py

🟡 **L285** [技术债务]: , should merge_pieces do this?

🟡 **L711** [技术债务]: transformations??

🟡 **L712** [技术债务]: only copy DataFrames when modification necessary

🟡 **L1061** [技术债务]: can we pin down take_left's type earlier?

🟡 **L1071** [技术债务]: can we pin down take_right's type earlier?

🟡 **L1095** [技术债务]: (non-nano) Workaround for common_type not dealing

🟡 **L1302** [技术债务]: what about other NAs?

🟡 **L2097** [技术债务]: why do we do this for AsOfMerge but not the others?

🟡 **L2218** [技术债务]: can we reuse a tolerance-conversion function from

🟡 **L2225** [技术债务]: we have no test cases with PeriodDtype here; probably

🟡 **L2450** [技术债务]: if either is a RangeIndex, we can likely factorize more efficiently?

🟡 **L2550** [技术债务]: Remove when we have a Factorizer for Arrow


### venv/lib/python3.13/site-packages/pandas/core/reshape/concat.py

🟡 **L534** [技术债务]: retain levels?


### venv/lib/python3.13/site-packages/pandas/core/reshape/reshape.py

🟡 **L229** [技术债务]: in all tests we have mask.any(0).all(); can we rely on that?

🟡 **L262** [技术债务]: Under what circumstances can we rely on sorted_values

🟡 **L793** [技术债务]: (EA2D): won't need special case, can go through .values


### venv/lib/python3.13/site-packages/pandas/core/reshape/melt.py

🟡 **L477** [技术债务]: anything else to catch?


### venv/lib/python3.13/site-packages/pandas/core/reshape/pivot.py

🟡 **L224** [技术债务]: can we avoid this?  this used to be handled by


### venv/lib/python3.13/site-packages/pandas/core/strings/accessor.py

🟡 **L186** [技术债务]: Dispatch all the methods

🟡 **L620** [技术债务]: dispatch

🟡 **L2026** [技术债务]: Add a similar _bytes interface.

🟡 **L2880** [技术债务]: dispatch


### venv/lib/python3.13/site-packages/pandas/core/strings/object_array.py

🟡 **L92** [技术债务]: this should be totally avoidable


### venv/lib/python3.13/site-packages/pandas/core/tools/datetimes.py

🟡 **L370** [技术债务]: Combine with above if DTI/DTA supports Arrow timestamps

🟡 **L392** [技术债务]: looks like we incorrectly raise with errors=="ignore"

🟡 **L1108** [技术债务]: avoid this kludge.


### venv/lib/python3.13/site-packages/pandas/core/array_algos/take.py

🟡 **L361** [技术债务]: if we get here with dt64/td64 we need to be sure we have


### venv/lib/python3.13/site-packages/pandas/core/array_algos/putmask.py

🟡 **L78** [技术债务]: this prob needs some better checking for 2D cases


### venv/lib/python3.13/site-packages/pandas/core/array_algos/replace.py

🟡 **L85** [技术债务]: should use missing.mask_missing?


### venv/lib/python3.13/site-packages/pandas/core/interchange/from_dataframe.py

🟡 **L470** [技术债务]: No DLPack yet, so need to construct a new ndarray from the data pointer


### venv/lib/python3.13/site-packages/pandas/core/interchange/dataframe_protocol.py

🟡 **L407** [技术债务]: not happy with Optional, but need to flag it may be expensive


### venv/lib/python3.13/site-packages/pandas/core/interchange/utils.py

🟡 **L139** [技术债务]: (infer_string) this should be LARGE_STRING for pyarrow storage,


### venv/lib/python3.13/site-packages/pandas/core/interchange/column.py

🟡 **L358** [技术债务]: this will need correcting

🟡 **L395** [技术债务]: maybe store as bit array to save space?..


### venv/lib/python3.13/site-packages/pandas/core/dtypes/cast.py

🟡 **L286** [技术债务]: complex?  what if result is already non-object?

🟡 **L411** [技术债务]: use tolerance like we do for float?

🟡 **L532** [技术债务]: (GH#45349): don't special-case IntervalDtype, allow

🟡 **L815** [技术债务]: test with datetime(2920, 10, 1) based on test_replace_dtypes

🟡 **L1058** [技术债务]: de-dup with maybe_cast_to_integer_array?

🟡 **L1082** [技术债务]: de-dup with maybe_cast_to_integer_array?

🟡 **L1228** [技术债务]: _from_sequence would raise ValueError in cases where

🟡 **L1285** [技术债务]: ValueError or TypeError? existing test

🟡 **L1293** [技术债务]: other value-dependent functions to standardize here include

🟡 **L1330** [技术债务]: do we need to recreate numpy's inspection logic for floats too

🟡 **L1383** [技术债务]: more generally, could do `not can_hold_na(dtype)`

🟡 **L1698** [技术债务]: (numpy-2.0 min): This case will raise an OverflowError above

🟡 **L1704** [技术债务]: can this be hit anymore after numpy 2.0?

🟡 **L1717** [技术债务]: Can this path be hit anymore with numpy > 2

🟡 **L1837** [技术债务]: general-case for EAs?

🟡 **L1860** [技术债务]: faster to check (element >=0).all()?  potential

🟡 **L1887** [技术债务]: itemsize check?

🟡 **L1944** [技术债务]: test tests.frame.methods.test_replace tests get here,


### venv/lib/python3.13/site-packages/pandas/core/dtypes/missing.py

🟡 **L520** [技术债务]: fastpath for pandas' StringDtype


### venv/lib/python3.13/site-packages/pandas/core/dtypes/dtypes.py

🟡 **L497** [技术债务]: hash_array doesn't handle mixed types. It casts

🟡 **L663** [技术债务]: we should figure out the expected return value in general

🟡 **L678** [技术债务]: should categorical always give an answer?

🟡 **L877** [技术债务]: update this.

🟡 **L1004** [技术债务]: (3.0): enforcing this will close GH#10575

🟡 **L2016** [技术债务]: for now only handle SparseDtypes and numpy dtypes => extend

🟡 **L2153** [技术债务]: Potentially change this & CategoricalDtype.type to

🟡 **L2165** [技术债务]: None? pd.NA? pa.null?

🟡 **L2305** [技术债务]: pa.types.is_boolean?


### venv/lib/python3.13/site-packages/pandas/core/dtypes/common.py

🟡 **L1532** [技术债务]: (jreback)


### venv/lib/python3.13/site-packages/pandas/core/groupby/generic.py

🟡 **L116** [技术债务]: (typing) the return value on this callable should be any *scalar*.

🟡 **L118** [技术债务]: validate types on ScalarResult and move to _typing

🟡 **L780** [技术债务]: should we do this inside II?

🟡 **L1595** [技术债务]: sure this is right?  we used to do this


### venv/lib/python3.13/site-packages/pandas/core/groupby/ops.py

🟡 **L477** [技术债务]: min_count

🟡 **L479** [技术债务]: should rank take result_mask?

🟡 **L775** [技术债务]: compress_group_index's second return value is int64, not intp


### venv/lib/python3.13/site-packages/pandas/core/groupby/grouper.py

🟡 **L358** [技术债务]: What are we assuming about subsequent calls?

🟡 **L443** [技术债务]: (3.0): enforcing these deprecations on Grouper should close

🟡 **L583** [技术债务]: can we unwrap this and get a tighter typing

🟡 **L588** [技术债务]: 2023-02-03 no test cases with len(newgrouper.groupings) > 1.

🟡 **L620** [技术债务]: 2022-10-08 we only have one test that gets here and

🟡 **L883** [技术债务]: These if-block and else-block are almost same.


### venv/lib/python3.13/site-packages/pandas/core/groupby/groupby.py

🟡 **L793** [技术债务]: Better repr for GroupBy object

🟡 **L1487** [技术债务]: can we reuse e.g. _reindex_non_unique?

🟡 **L1942** [技术债务]: Is this exactly right; see WrappedCythonOp get_result_dtype?

🟡 **L1992** [技术债务]: shouldn't min_count matter?

🟡 **L1993** [技术债务]: avoid special casing SparseArray here

🟡 **L1997** [技术债务]: re-raise as TypeError?  should not be reached

🟡 **L2337** [技术债务]: (EA2D): reshape would not be necessary with 2D EAs

🟡 **L3062** [技术债务]: For DataFrames what if columns are mixed arrow/numpy/masked?

🟡 **L5443** [技术债务]: (GH#23918): Remove this conditional for SeriesGroupBy when


### venv/lib/python3.13/site-packages/pandas/core/internals/concat.py

🟡 **L114** [技术债务]: (ArrayManager) this assumes that all managers are of the same type

🟡 **L137** [技术债务]: support more dtypes here.  This will be simpler once

🟡 **L179** [技术债务]: (EA2D): special-casing not needed with 2D EAs

🟡 **L339** [技术债务]: in all extant test cases 2023-04-08 we have a slice here.

🟡 **L377** [技术债务]: this will need updating if we ever have non-nano dt64/td64

🟡 **L381** [技术债务]: kludge; test_append_empty_frame_with_timedelta64ns_nat

🟡 **L386** [技术债务]: better to use can_hold_element?

🟡 **L407** [技术债务]: (EA2D): no need for special case with 2D EAs

🟡 **L472** [技术债务]: (EA2D): special case not needed if all EAs used HybridBlocks


### venv/lib/python3.13/site-packages/pandas/core/internals/construction.py

🟡 **L397** [技术债务]: check len(values) == 0?

🟡 **L552** [技术债务]: check for length-zero range, in which case return int64 dtype?

🟡 **L553** [技术债务]: reuse anything in try_cast?

🟡 **L820** [技术债务]: is that an issue with numpy?

🟡 **L1056** [技术债务]: test(s) that get here

🟡 **L1057** [技术债务]: try to de-duplicate this convert function with


### venv/lib/python3.13/site-packages/pandas/core/internals/array_manager.py

🟡 **L366** [技术债务]: what is this used for?

🟡 **L376** [技术债务]: copy?

🟡 **L731** [技术债务]: can we avoid needing to unpack this here? That means converting

🟡 **L737** [技术债务]: we receive a datetime/timedelta64 ndarray from DataFrame._iset_item

🟡 **L814** [技术债务]: self.arrays can be empty

🟡 **L817** [技术债务]: is this copy needed?

🟡 **L893** [技术债务]: NaT doesn't preserve dtype, so we need to ensure to create

🟡 **L913** [技术债务]: what if `other` is BlockManager ?

🟡 **L1059** [技术债务]: (ArrayManager) doesn't yet preserve the correct dtype

🟡 **L1332** [技术债务]: decide on exact behaviour (we shouldn't do this only for empty result)


### venv/lib/python3.13/site-packages/pandas/core/internals/ops.py

🟡 **L120** [技术债务]: (EA2D): with 2D EAs only this first clause would be needed


### venv/lib/python3.13/site-packages/pandas/core/internals/blocks.py

🟡 **L420** [技术债务]: (EA2D): unnecessary with 2D EAs

🟡 **L556** [技术债务]: does it matter that self.dtype might not match blocks[i].dtype?

🟡 **L877** [技术债务]: avoid special-casing

🟡 **L905** [技术债务]: (CoW): Maybe split here as well into columns where mask has True

🟡 **L1092** [技术债务]: avoid special-casing

🟡 **L1424** [技术债务]: in all tests we have mask.all(); can we rely on that?

🟡 **L1482** [技术债务]: avoid having to construct values[indexer]

🟡 **L1851** [技术债务]: (3.0): this case will not be reachable once GH#53638 is enforced

🟡 **L1896** [技术债务]: (EA2D): transpose will be unnecessary with 2D EAs

🟡 **L1982** [技术债务]: round only defined on BaseMaskedArray

🟡 **L2027** [技术债务]: (CoW): This is tricky, if parent block goes out of scope

🟡 **L2123** [技术债务]: (GH#45419): string[pyarrow] tests break if we transpose

🟡 **L2325** [技术债务]: (EA2D): reshape not needed with 2D EAs

🟡 **L2440** [技术债务]: (EA2D): override unnecessary with 2D EAs

🟡 **L2455** [技术债务]: (EA2D): unnecessary with 2D EAs

🟡 **L2489** [技术债务]: (EA2D): unnecessary with 2D EAs

🟡 **L2496** [技术债务]: should we avoid getting here with DataFrame?

🟡 **L2508** [技术债务]: ATM this doesn't work for iget/_slice, can we change that?

🟡 **L2511** [技术债务]: (EA2D): not needed with 2D EAs

🟡 **L2575** [技术债务]: (EA2D): won't be necessary with 2D EAs

🟡 **L2582** [技术债务]: (EA2D): won't be necessary with 2D EAs

🟡 **L2633** [技术债务]: could cast to object depending on fill_value?

🟡 **L2674** [技术债务]: (3.0): delete and remove deprecation in __init__.py.

🟡 **L2680** [技术债务]: (3.0): delete and remove deprecation in __init__.py.

🟡 **L2830** [技术债务]: (EA2D): special case not needed with 2D EAs

🟡 **L2842** [技术债务]: (EA2D): special case unnecessary with 2D EAs

🟡 **L2856** [技术债务]: (EA2D): special case not needed with 2D EAs

🟡 **L2891** [技术债务]: (EA2D): https://github.com/pandas-dev/pandas/issues/23023

🟡 **L2921** [技术债务]: (CoW) we should also mark our ExtensionArrays as read-only


### venv/lib/python3.13/site-packages/pandas/core/internals/base.py

🟡 **L66** [技术债务]: share more methods/attributes

🟡 **L398** [技术债务]: https://github.com/pandas-dev/pandas/issues/22791


### venv/lib/python3.13/site-packages/pandas/core/internals/managers.py

🟡 **L555** [技术债务]: optimization potential

🟡 **L768** [技术债务]: (EA2D): special casing unnecessary with 2D EAs

🟡 **L990** [技术债务]: this could be wrong if blk.mgr_locs is not slice(None)-like;

🟡 **L1008** [技术债务]: use object dtype as workaround for non-performant

🟡 **L1052** [技术债务]: (CoW) making the arrays read-only might make this safer to use?

🟡 **L1074** [技术债务]: (EA2D): special casing not needed with 2D EAs

🟡 **L1097** [技术债务]: refactor, clearly separate broadcasting & zip-like assignment

🟡 **L1124** [技术债务]: fastest way to check this?

🟡 **L1202** [技术债务]: (EA2D): special casing unnecessary with 2D EAs

🟡 **L1378** [技术债务]: re-issue this with setitem-specific message?

🟡 **L1649** [技术债务]: (EA2D): the combine will be unnecessary with 2D EAs

🟡 **L1934** [技术债务]: (EA2D): ndim would be unnecessary with 2D EAs

🟡 **L1984** [技术债务]: (CoW) in theory only need to track reference if new_array is a view

🟡 **L2002** [技术债务]: this method is only used in groupby SeriesSplitter at the moment,

🟡 **L2302** [技术债务]: optimization potential in case all mgrs contain slices and

🟡 **L2380** [技术债务]: no tests get here, a handful would if we disabled


### venv/lib/python3.13/site-packages/pandas/core/computation/pytables.py

🟡 **L441** [技术债务]: return None might never be reached


### venv/lib/python3.13/site-packages/pandas/core/computation/eval.py

🟡 **L66** [技术债务]: validate this in a more general way (thinking of future engines


### venv/lib/python3.13/site-packages/pandas/core/_numba/extensions.py

🟡 **L66** [技术债务]: Range index support

🟡 **L364** [技术债务]: preserve the original class for the index

🟡 **L450** [技术债务]: Check index matching?


### venv/lib/python3.13/site-packages/pandas/core/_numba/executor.py

🟡 **L125** [技术债务]: Preserve complex dtypes


### venv/lib/python3.13/site-packages/pandas/core/window/rolling.py

🟡 **L391** [技术债务]: sure we want to overwrite results?

🟡 **L409** [技术债务]: why do we get here with e.g. MultiIndex?

🟡 **L651** [技术债务]: Could preserve correct dtypes in future


### venv/lib/python3.13/site-packages/pandas/core/arrays/categorical.py

🟡 **L2147** [技术债务]: GH#15362


### venv/lib/python3.13/site-packages/pandas/core/arrays/interval.py

🟡 **L858** [技术债务]: in an IntervalIndex we can reuse the cached

🟡 **L862** [技术债务]: other cases we can use lexsort for?  much more performant.

🟡 **L909** [技术债务]: (3.0): after EA.fillna 'method' deprecation is enforced, we can remove

🟡 **L1195** [技术债务]: check subdtype match like _validate_setitem_value?

🟡 **L1921** [技术债务]: should we just cast these to list?


### venv/lib/python3.13/site-packages/pandas/core/arrays/datetimes.py

🟡 **L286** [技术债务]: require any NAs be valid-for-DTA

🟡 **L287** [技术债务]: if dtype is passed, check for tzawareness compat?

🟡 **L716** [技术债务]: preserve freq?

🟡 **L817** [技术债务]: (GH#55564): as_unit will be unnecessary

🟡 **L1376** [技术债务]: no tests that check for dtype of result as of 2024-08-15

🟡 **L2247** [技术债务]: We do not have tests specific to string-dtypes,

🟡 **L2344** [技术债务]: better way to handle this?  non-copying alternative?

🟡 **L2352** [技术债务]: if tz is UTC, are there situations where we *don't* want a

🟡 **L2490** [技术债务]: We have no tests for these


### venv/lib/python3.13/site-packages/pandas/core/arrays/string_.py

🟡 **L207** [技术债务]: should dtype == "string" work for the NaN variant?

🟡 **L390** [技术债务]: (4.0): Once the deprecation here is enforced, this method can be

🟡 **L419** [技术债务]: require any NAs be valid-for-string

🟡 **L553** [技术债务]: we could alternatively do this check before map_infer_mask

🟡 **L1127** [技术债务]: validate or force NA/None to NaN


### venv/lib/python3.13/site-packages/pandas/core/arrays/numpy_.py

🟡 **L309** [技术债务]: assert we have floating dtype?


### venv/lib/python3.13/site-packages/pandas/core/arrays/string_arrow.py

🟡 **L75** [技术债务]: Inherit directly from BaseStringArrayMethods. Currently we inherit from

🟡 **L380** [技术债务]: flags passed separately by user are ignored


### venv/lib/python3.13/site-packages/pandas/core/arrays/masked.py

🟡 **L290** [技术债务]: get this all from np_can_hold_element?

🟡 **L302** [技术债务]: unsigned checks

🟡 **L376** [技术债务]: need to make sure we have the same order for data/mask

🟡 **L559** [技术债务]: deal with NaNs for FloatingArray case

🟡 **L562** [技术债务]: Is rounding what we want long term?

🟡 **L724** [技术债务]: need test for BooleanArray needing a copy

🟡 **L802** [技术债务]: (GH#30188) ATM we don't match the behavior of non-masked

🟡 **L974** [技术债务]: (jreback) what if we have a non-na float as a fill value?

🟡 **L1165** [技术债务]: (GH#40932): na_value_for_dtype(self.dtype.numpy_dtype)


### venv/lib/python3.13/site-packages/pandas/core/arrays/period.py

🟡 **L702** [技术债务]: other cases?

🟡 **L897** [技术债务]: can we de-duplicate with Period._add_timedeltalike_scalar?


### venv/lib/python3.13/site-packages/pandas/core/arrays/datetimelike.py

🟡 **L350** [技术债务]: Remove Datetime & DatetimeTZ formatters.

🟡 **L545** [技术债务]: try to de-duplicate these, ensure identical behavior

🟡 **L717** [技术债务]: do we need equal dtype or just comparable?

🟡 **L785** [技术债务]: de-duplicate with equals, validate_comparison_value

🟡 **L1002** [技术债务]: handle 2D-like listlikes

🟡 **L1526** [技术债务]: Can we simplify/generalize these cases at all?

🟡 **L2006** [技术债务]: we only have tests for this for DTA, not TDA (2022-07-01)

🟡 **L2205** [技术债务]: annotate other as DatetimeArray | TimedeltaArray | Timestamp | Timedelta

🟡 **L2342** [技术债务]: copy or view?

🟡 **L2442** [技术债务]: can we reuse is_date_array_normalized?  would need a skipna kwd

🟡 **L2483** [技术债务]: cases where we need to do another pass through maybe_convert_dtype,


### venv/lib/python3.13/site-packages/pandas/core/arrays/_mixins.py

🟡 **L363** [技术债务]: NumpyExtensionArray didn't used to copy, need tests

🟡 **L511** [技术债务]: disable for Categorical if not ordered?

🟡 **L523** [技术债务]: technically __init__ isn't defined here.


### venv/lib/python3.13/site-packages/pandas/core/ops/array_ops.py

🟡 **L234** [技术债务]: can remove this after dropping some future numpy version?

🟡 **L275** [技术债务]: we should handle EAs consistently and move this check before the if/else

🟡 **L317** [技术债务]: make this treatment consistent across ops and classes.

🟡 **L332** [技术债务]: but not pd.NA?


### venv/lib/python3.13/site-packages/pandas/core/indexes/interval.py

🟡 **L685** [技术债务]: DO this in maybe_booleans_to_slice?

🟡 **L935** [技术债务]: arithmetic operations


### venv/lib/python3.13/site-packages/pandas/core/indexes/range.py

🟡 **L1108** [技术债务]: if other is a RangeIndex we may have more efficient options


### venv/lib/python3.13/site-packages/pandas/core/indexes/datetimes.py

🟡 **L98** [技术债务]: If we knew what was going in to **d, we might be able to


### venv/lib/python3.13/site-packages/pandas/core/indexes/multi.py

🟡 **L2996** [技术债务]: need is_valid_na_for_dtype(key, level_index.dtype)

🟡 **L3069** [技术债务]: what if we have an IntervalIndex level?

🟡 **L3211** [技术债务]: we should be only dropping levels on which we are

🟡 **L3255** [技术债务]: in some cases we still need to drop some levels,

🟡 **L3268** [技术债务]: why?

🟡 **L3296** [技术债务]: this message can be inaccurate, e.g.

🟡 **L3531** [技术债务]: how to handle IntervalIndex level? (no test cases)

🟡 **L3848** [技术债务]: what if they both have np.nan for their names?


### venv/lib/python3.13/site-packages/pandas/core/indexes/api.py

🟡 **L145** [技术债务]: handle index names!

🟡 **L291** [技术债务]: this behavior is not tested (so may not be desired),

🟡 **L306** [技术债务]: what about Categorical[dt64]?


### venv/lib/python3.13/site-packages/pandas/core/indexes/period.py

🟡 **L302** [技术债务]: We can do some of these with no-copy / coercion?


### venv/lib/python3.13/site-packages/pandas/core/indexes/frozen.py

🟡 **L70** [技术债务]: Consider deprecating these in favor of `union` (xref gh-15506)


### venv/lib/python3.13/site-packages/pandas/core/indexes/datetimelike.py

🟡 **L230** [技术债务]: not reached in tests 2023-10-11

🟡 **L335** [技术债务]: does this depend on being monotonic _increasing_?

🟡 **L424** [技术债务]: com.asarray_tuplesafe shouldn't cast e.g. DatetimeArray

🟡 **L551** [技术债务]: (GH#41493): we cannot just do

🟡 **L652** [技术债务]: do union on the reversed indexes?


### venv/lib/python3.13/site-packages/pandas/core/indexes/base.py

🟡 **L1465** [技术债务]: why do we need different justify for these cases?

🟡 **L2775** [技术债务]: (ExtensionIndex): 3rd party EA might override?

🟡 **L3558** [技术债务]: algos.unique1d should preserve DTA/TDA

🟡 **L4418** [技术债务]: tests where passing `keep_order=not self._is_multi`

🟡 **L5091** [技术债务]: exclude RangeIndex (which allocates memory)?

🟡 **L5210** [技术债务]: (ExtensionIndex): remove special-case, just use self._values

🟡 **L5228** [技术债务]: exclude ABCRangeIndex case here as it copies

🟡 **L5638** [技术债务]: (infer_string) can we avoid this special case?

🟡 **L6150** [技术债务]: if object, could use infer_dtype to preempt costly

🟡 **L6158** [技术债务]: get_indexer has fastpaths for both Categorical-self and

🟡 **L6358** [技术债务]: we dont have tests that get here

🟡 **L6365** [技术债务]: may need itemsize check if we have non-64-bit Indexes

🟡 **L6469** [技术债务]: this was written assuming we only get here with object-dtype,

🟡 **L6488** [技术债务]: if we are a MultiIndex, we can do better

🟡 **L6565** [技术债务]: De-duplicate with map, xref GH#32349

🟡 **L7003** [技术债务]: (__array_function__): special casing will be unnecessary

🟡 **L7239** [技术债务]: should set MultiIndex._can_hold_na = False?

🟡 **L7427** [技术债务]: (3.0): PeriodArray and DatetimeArray any/all will raise,

🟡 **L7875** [技术债务]: tests that get here in column path

🟡 **L7881** [技术债务]: tests that get here in column path


### venv/lib/python3.13/site-packages/pandas/core/arrays/arrow/accessors.py

🟡 **L151** [技术债务]: Support negative key but pyarrow does not allow

🟡 **L163** [技术债务]: Support negative start/stop/step, ideally this would be added

🟡 **L167** [技术债务]: When adding negative step support


### venv/lib/python3.13/site-packages/pandas/core/arrays/arrow/array.py

🟡 **L134** [技术债务]: Replace with pyarrow floordiv kernel.

🟡 **L538** [技术债务]: Move logic in _from_sequence_of_strings into

🟡 **L581** [技术债务]: (infer_string) should this be large_string?

🟡 **L599** [技术债务]: should be handled by pyarrow?

🟡 **L919** [技术债务]: maybe complex? object?

🟡 **L1130** [技术债务]: (CoW): Not necessary anymore when CoW is the default

🟡 **L1147** [技术债务]: (3.0): after EA.fillna 'method' deprecation is enforced, we can remove

🟡 **L1164** [技术债务]: (CoW): Not necessary anymore when CoW is the default

🟡 **L1387** [技术债务]: (ARROW-9433): Treat negative indices as NULL

🟡 **L1402** [技术债务]: (ARROW-9432): Treat negative indices as indices from the right.


### venv/lib/python3.13/site-packages/pandas/core/arrays/sparse/array.py

🟡 **L384** [技术债务]: make kind=None, and use data.kind?

🟡 **L419** [技术债务]: disentangle the fill_value dtype inference from

🟡 **L422** [技术债务]: What should the empty dtype be? Object or float?

🟡 **L442** [技术债务]: avoid double copy when dtype forces cast.

🟡 **L599** [技术债务]: (SparseArray.__setitem__): remove special cases in

🟡 **L744** [技术债务]: (3.0): We can remove this method once deprecation for fillna method

🟡 **L1199** [技术债务]: wraparound

🟡 **L1801** [技术债务]: make this more flexible than just ndarray...

🟡 **L1922** [技术债务]: copy


### venv/lib/python3.13/site-packages/pandas/io/parsers/readers.py

🟡 **L1654** [技术债务]: Refactor this logic, its pretty convoluted


### venv/lib/python3.13/site-packages/pandas/io/parsers/python_parser.py

🟡 **L461** [技术债务]: Use pandas.io.common.dedup_names instead (see #50371)


### venv/lib/python3.13/site-packages/pandas/io/parsers/base_parser.py

🟡 **L813** [技术债务]: this is for consistency with

🟡 **L849** [技术债务]: why skipna=True here and False above? some tests depend

🟡 **L1117** [技术债务]: We could return default_index(0) if dtype_dict[name] is None

🟡 **L1234** [技术债务]: not reached in tests 2023-10-27; needed?


### venv/lib/python3.13/site-packages/pandas/io/formats/html.py

🟡 **L337** [技术债务]: Refactor to remove code duplication with code

🟡 **L344** [技术债务]: Refactor to use _get_column_name_list from

🟡 **L370** [技术债务]: Refactor to remove code duplication with code block

🟡 **L377** [技术债务]: Refactor to use _get_column_name_list from


### venv/lib/python3.13/site-packages/pandas/io/formats/format.py

🟡 **L1227** [技术债务]: (3.0): this will be unreachable when use_inf_as_na

🟡 **L1681** [技术债务]: nat_rep is never passed, na_rep is.


### venv/lib/python3.13/site-packages/pandas/io/formats/excel.py

🟡 **L238** [技术债务]: handle cell width and height: needs support in pandas.io.excel

🟡 **L254** [技术债务]: text-indent, padding-left -> alignment.indent

🟡 **L362** [技术债务]: perhaps allow for special properties


### venv/lib/python3.13/site-packages/pandas/io/formats/style_render.py

🟡 **L878** [技术债务]: try to consolidate the concat visible rows


### venv/lib/python3.13/site-packages/pandas/io/formats/css.py

🟡 **L106** [技术债务]: Can we use current color as initial value to comply with CSS standards?

🟡 **L119** [技术债务]: Warn user if item entered more than once (e.g. "border: red green")

🟡 **L334** [技术债务]: support %

🟡 **L412** [技术债务]: don't lowercase case sensitive parts of values (strings)


### venv/lib/python3.13/site-packages/pandas/io/excel/_pyxlsb.py

🟡 **L63** [技术债务]: hack in buffer capability

🟡 **L84** [技术债务]: there is no way to distinguish between floats and datetimes in pyxlsb


### venv/lib/python3.13/site-packages/pandas/io/excel/_xlsxwriter.py

🟡 **L134** [技术债务]: support other fill patterns


### venv/lib/python3.13/site-packages/pandas/io/json/_json.py

🟡 **L374** [技术债务]: Do this timedelta properly in objToJSON.c See GH #15137


### venv/lib/python3.13/site-packages/pandas/io/json/_normalize.py

🟡 **L466** [技术债务]: handle record value which are lists, at least error


### venv/lib/python3.13/site-packages/pandas/io/clipboard/__init__.py

🟡 **L274** [技术债务]: https://github.com/asweigart/pyperclip/issues/43

🟡 **L539** [技术债务]: (pyperclip#55): pyperclip currently does not support Cygwin,

🟡 **L621** [技术债务]: - split this into 'qtpy', 'pyqt4', and 'pyqt5'


### venv/lib/python3.13/site-packages/pandas/tests/series/test_logical_ops.py

🟡 **L433** [技术债务]: (infer_string) should this behave differently?

🟡 **L533** [技术债务]: this belongs in comparison tests


### venv/lib/python3.13/site-packages/pandas/tests/series/test_constructors.py

🟡 **L571** [技术债务]: should this be raising at all?

🟡 **L591** [技术债务]: should this be raising at all?

🟡 **L706** [技术债务]: (ArrayManager) rewrite test

🟡 **L848** [技术债务]: try to align these

🟡 **L1207** [技术债务]: GH#19223 was about .astype, doesn't belong here

🟡 **L2200** [技术债务]: make this not cast to object in pandas 3.0


### venv/lib/python3.13/site-packages/pandas/tests/series/test_ufunc.py

🟡 **L173** [技术债务]: np.modf, np.frexp

🟡 **L269** [技术债务]: cases with NAs, axis kwarg for DataFrame

🟡 **L349** [技术债务]: cases with axis kwarg

🟡 **L455** [技术债务]: (CoW) see https://github.com/pandas-dev/pandas/pull/51082


### venv/lib/python3.13/site-packages/pandas/tests/series/test_arithmetic.py

🟡 **L763** [技术债务]: belongs in tests/arithmetic?


### venv/lib/python3.13/site-packages/pandas/tests/reshape/test_cut.py

🟡 **L584** [技术债务]: constructing DatetimeIndex with dtype="M8[s]" without truncating


### venv/lib/python3.13/site-packages/pandas/tests/strings/test_cat.py

🟡 **L359** [技术债务]: Strimg option, this should return string dtype


### venv/lib/python3.13/site-packages/pandas/tests/strings/test_split_partition.py

🟡 **L385** [技术债务]: see GH 18463


### venv/lib/python3.13/site-packages/pandas/tests/strings/test_find_replace.py

🟡 **L258** [技术债务]: (infer_string)

🟡 **L306** [技术债务]: this currently works for pyarrow-backed dtypes but raises for python

🟡 **L322** [技术债务]: should this be supported?

🟡 **L959** [技术债务]: this currently works for pyarrow-backed dtypes but raises for python

🟡 **L1085** [技术债务]: this currently works for pyarrow-backed dtypes but raises for python


### venv/lib/python3.13/site-packages/pandas/tests/strings/test_extract.py

🟡 **L19** [技术债务]: should this raise TypeError


### venv/lib/python3.13/site-packages/pandas/tests/tools/test_to_datetime.py

🟡 **L591** [技术债务]: Timestamp raises ValueError("could not convert string to Timestamp")

🟡 **L1179** [技术债务]: behavior should not depend on cache

🟡 **L1194** [技术债务]: shouldn't depend on cache!

🟡 **L1208** [技术债务]: shouldn't depend on cache!


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_masked.py

🟡 **L267** [技术债务]: patching self is a bad pattern here

🟡 **L272** [技术债务]: can we make this boolean?

🟡 **L294** [技术债务]: prod with integer dtypes does *not* match the result we would

🟡 **L318** [技术债务]: Why does Window Numpy 2.0 dtype depend on skipna?

🟡 **L378** [技术债务]: xfail?


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_sparse.py

🟡 **L254** [技术债务]: this fails bc we do not pass through data_missing. If we did,

🟡 **L385** [技术债务]: this fails bc we do not pass through nullable_string_dtype;


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_string.py

🟡 **L247** [技术债务]: (infer_string)


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_categorical.py

🟡 **L80** [技术债务]: Is this deliberate?


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_interval.py

🟡 **L119** [技术债务]: either belongs in tests.arrays.interval or move into base tests.


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_numpy.py

🟡 **L219** [技术债务]: NumpyExtensionArray.searchsorted calls ndarray.searchsorted which

🟡 **L353** [技术债务]: there is some issue with NumpyExtensionArray, therefore,


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_arrow.py

🟡 **L267** [技术债务]: skip otherwise?

🟡 **L507** [技术债务]: in the opposite case, aren't we testing... nothing? For

🟡 **L512** [技术债务]: in the opposite case, aren't we testing... nothing?

🟡 **L859** [技术债务]: why is this different vs date32?

🟡 **L885** [技术债务]: would it make more sense to retain Decimal here?

🟡 **L892** [技术债务]: would it make more sense to retain Decimal here?

🟡 **L3218** [技术债务]: repr value may not be expected; address how


### venv/lib/python3.13/site-packages/pandas/tests/resample/test_period_index.py

🟡 **L299** [技术债务]: should this raise at the resample call instead of at the mean call?

🟡 **L453** [技术债务]: don't leave commented-out

🟡 **L906** [技术债务]: is non-tick the relevant characteristic? (GH 33815)


### venv/lib/python3.13/site-packages/pandas/tests/resample/test_base.py

🟡 **L244** [技术债务]: no tests with len(df.columns) > 0


### venv/lib/python3.13/site-packages/pandas/tests/resample/test_time_grouper.py

🟡 **L250** [技术债务]: is this desired?


### venv/lib/python3.13/site-packages/pandas/tests/util/test_assert_almost_equal.py

🟡 **L341** [技术债务]: to get the same deprecation in assert_numpy_array_equal we need

🟡 **L343** [技术债务]: to get the same deprecation in assert_index_equal we need to


### venv/lib/python3.13/site-packages/pandas/tests/io/test_parquet.py

🟡 **L53** [技术债务]: (ArrayManager) fastparquet relies on BlockManager internals


### venv/lib/python3.13/site-packages/pandas/tests/io/test_fsspec.py

🟡 **L199** [技术债务]: (ArrayManager) fastparquet

🟡 **L259** [技术债务]: (ArrayManager) fastparquet


### venv/lib/python3.13/site-packages/pandas/tests/io/test_clipboard.py

🟡 **L354** [技术债务]: avoid this exception?


### venv/lib/python3.13/site-packages/pandas/tests/io/test_stata.py

🟡 **L188** [技术债务]: don't leave commented-out

🟡 **L194** [技术债务]: don't leave commented-out


### venv/lib/python3.13/site-packages/pandas/tests/io/test_sql.py

🟡 **L1874** [技术债务]: is this astype safe?

🟡 **L1927** [技术债务]: Postgres stores an INTERVAL, which ADBC reads as a Month-Day-Nano

🟡 **L3551** [技术债务]: (GH#36893) fill this in when we add more engines


### venv/lib/python3.13/site-packages/pandas/tests/io/test_http_headers.py

🟡 **L105** [技术债务]: (ArrayManager) fastparquet


### venv/lib/python3.13/site-packages/pandas/tests/io/test_spss.py

🟡 **L14** [技术债务]: (CoW) - detection of chained assignment in cython


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_methods.py

🟡 **L152** [技术债务]: copy=False without CoW still returns a copy in this case

🟡 **L1013** [技术债务]: (CoW): Block splitting causes references here

🟡 **L1205** [技术债务]: Make inplace by using out parameter of ndarray.round?

🟡 **L1208** [技术债务]: Cannot rely on Numpy returning view after version 2.3

🟡 **L1496** [技术债务]: (CoW): Could split blocks to avoid copying the whole block

🟡 **L1824** [技术债务]: (CoW) better warning message?


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_chained_assignment_deprecation.py

🟡 **L77** [技术债务]: (CoW-warn) because of the usage of *args, this doesn't warn on Py3.11+

🟡 **L139** [技术债务]: (CoW-warn) ideally also warns on the default mode, but the ser' _cacher

🟡 **L145** [技术债务]: (CoW-warn) expand the cases


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_indexing.py

🟡 **L816** [技术债务]: add more tests modifying the parent

🟡 **L1023** [技术债务]: (CoW-warn) assert the FutureWarning for CoW is also raised

🟡 **L1101** [技术债务]: add tests for other indexing methods on the Series


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_astype.py

🟡 **L271** [技术债务]: the default nullable string dtype still uses python storage


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_replace.py

🟡 **L23** [技术债务]: Add these in a further optimization

🟡 **L106** [技术债务]: Block splitting would allow us to avoid copying b

🟡 **L119** [技术债务]: This should split and not copy the whole block


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_core_functionalities.py

🟡 **L54** [技术债务]: (CoW-warn) false positive? -> block gets split because of `df["b"] = 100`


### venv/lib/python3.13/site-packages/pandas/tests/interchange/test_utils.py

🟡 **L7** [技术债务]: use ArrowSchema to get reference C-string.


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_block_internals.py

🟡 **L30** [技术债务]: (ArrayManager) check which of those tests need to be rewritten to test the

🟡 **L222** [技术债务]: don't leave commented-out

🟡 **L237** [技术债务]: don't leave commented-out

🟡 **L352** [技术债务]: (wesm): Unclear how exactly this is related to internal matters


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_logical_ops.py

🟡 **L155** [技术债务]: belongs elsewhere


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_reductions.py

🟡 **L1774** [技术债务]: np.median(df, axis=0) gives np.array([2.0, 2.0]) instead

🟡 **L1880** [技术债务]: why does min_count=1 impact the resulting Windows dtype


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_constructors.py

🟡 **L317** [技术债务]: (CoW-warn) this should warn

🟡 **L2108** [技术债务]: (2.0): ideally we should get the same 'expected' without passing

🟡 **L2224** [技术债务]: can be replaced with `df.loc[:, "A"] = 5` after deprecation about

🟡 **L2377** [技术债务]: (ArrayManager) astype to bytes dtypes does not yet give object dtype

🟡 **L2569** [技术债务]: (ArrayManager) properly honor copy keyword for dict input

🟡 **L2625** [技术债务]: most of the rest of this test belongs in indexing tests

🟡 **L2636** [技术债务]: (GH#35417): until GH#35417, iloc.setitem into EA values does not preserve

🟡 **L2650** [技术债务]: (GH#35417): enable after GH#35417

🟡 **L2653** [技术债务]: we can call check_views if we stop consolidating

🟡 **L2656** [技术债务]: we can check b[0] == 0 if we stop consolidating in

🟡 **L2875** [技术债务]: not clear if these raising is desired (no extant tests),

🟡 **L3161** [技术债务]: make this not cast to object in pandas 3.0

🟡 **L3180** [技术债务]: make a helper in tm?

🟡 **L3348** [技术债务]: better location for this test?


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_unary.py

🟡 **L167** [技术债务]: assert that we have copies?


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_cumulative.py

🟡 **L31** [技术债务]: (wesm): do something with this?


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_ufunc.py

🟡 **L150** [技术债务]: (FloatArray): this will be Float64Dtype.


### venv/lib/python3.13/site-packages/pandas/tests/frame/test_arithmetic.py

🟡 **L304** [技术债务]: test_bool_flex_frame needs a better name

🟡 **L899** [技术债务]: (ArrayManager) decide on dtypes

🟡 **L926** [技术债务]: (ArrayManager) decide on dtypes

🟡 **L1276** [技术债务]: not sure what's correct here.


### venv/lib/python3.13/site-packages/pandas/tests/libs/test_hashtable.py

🟡 **L264** [技术债务]: moved from test_algos; may be redundancies with other tests


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_timegrouper.py

🟡 **L747** [技术债务]: can we retain second reso in .apply here?


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_grouping.py

🟡 **L936** [技术债务]: should prob allow a str of Interval work as well


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_reductions.py

🟡 **L747** [技术债务]: For skipna=False, bool(pd.NA) raises; should groupby?

🟡 **L750** [技术债务]: Should be more consistent - return Int64 when dtype.na_value is pd.NA?


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_categorical.py

🟡 **L94** [技术债务]: split this test


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_raises.py

🟡 **L634** [技术债务]: empty_groups should be true due to unobserved categorical combinations


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_apply.py

🟡 **L461** [技术债务]: (GH#34306): Use assert_frame_equal when column name is not np.nan


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_groupby_dropna.py

🟡 **L612** [技术债务]: Should this be 3?


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_groupby.py

🟡 **L313** [技术债务]: try to get this more consistent?

🟡 **L565** [技术债务]: groupby get drops names

🟡 **L2165** [技术债务]: test the numeric_only=True case

🟡 **L3206** [技术债务]: check groupby with > 1 col ?


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_numeric_only.py

🟡 **L93** [技术债务]: min, max *should* handle


### venv/lib/python3.13/site-packages/pandas/tests/internals/test_internals.py

🟡 **L48** [技术债务]: (ArrayManager) factor out interleave_dtype tests

🟡 **L1285** [技术债务]: check this holds for all blocks


### venv/lib/python3.13/site-packages/pandas/tests/computation/test_eval.py

🟡 **L102** [技术债务]: using range(5) here is a kludge

🟡 **L299** [技术债务]: update testing code so that assert_almost_equal statement

🟡 **L592** [技术债务]: 2022-01-29: result return list with numexpr 2.7.3 in CI

🟡 **L1289** [技术债务]: 2022-01-29: Name check failed with numexpr 2.7.3 in CI


### venv/lib/python3.13/site-packages/pandas/tests/plotting/test_datetimelike.py

🟡 **L1318** [技术债务]: color cycle problems

🟡 **L1386** [技术债务]: color cycle problems

🟡 **L1407** [技术债务]: color cycle problems

🟡 **L1428** [技术债务]: color cycle problems

🟡 **L1754** [技术债务]: do something more intelligent


### venv/lib/python3.13/site-packages/pandas/tests/window/test_expanding.py

🟡 **L576** [技术债务]: xref gh-15826


### venv/lib/python3.13/site-packages/pandas/tests/window/test_pairwise.py

🟡 **L299** [技术债务]: We're missing a flag somewhere in meson


### venv/lib/python3.13/site-packages/pandas/tests/arrays/test_datetimelike.py

🟡 **L33** [技术债务]: more freq variants

🟡 **L49** [技术债务]: non-monotone indexes; NaTs, different start dates

🟡 **L69** [技术债务]: non-monotone indexes; NaTs, different start dates, timezones

🟡 **L82** [技术债务]: flesh this out

🟡 **L148** [技术债务]: we should probably get the same behavior regardless?

🟡 **L663** [技术债务]: GH 57739

🟡 **L984** [技术债务]: GH 57739


### venv/lib/python3.13/site-packages/pandas/tests/arrays/test_timedeltas.py

🟡 **L106** [技术债务]: 2022-07-11 this is the only test that gets to DTA.tz_convert


### venv/lib/python3.13/site-packages/pandas/tests/arrays/test_datetimes.py

🟡 **L93** [技术债务]: simplify once we can just .astype to other unit

🟡 **L173** [技术债务]: tests with td64

🟡 **L276** [技术债务]: merge this into tests/arithmetic/test_datetime64 once it is


### venv/lib/python3.13/site-packages/pandas/tests/arithmetic/test_period.py

🟡 **L208** [技术债务]: parameterize over boxes

🟡 **L226** [技术债务]: moved from test_datetime64; de-duplicate with version below

🟡 **L290** [技术债务]: could also box idx?

🟡 **L333** [技术债务]: Could parametrize over boxes for idx?

🟡 **L411** [技术债务]: De-duplicate with test_pi_cmp_nat

🟡 **L485** [技术债务]: needs parametrization+de-duplication

🟡 **L637** [技术债务]: parametrize over boxes for other?

🟡 **L831** [技术债务]: parametrize over box for pi?

🟡 **L1055** [技术债务]: Some of these are misnomers because of non-Tick DateOffsets


### venv/lib/python3.13/site-packages/pandas/tests/arithmetic/test_datetime64.py

🟡 **L161** [技术债务]: moved from tests.series.test_operators; needs cleanup

🟡 **L395** [技术债务]: moved from tests.indexes.test_base; parametrize and de-duplicate

🟡 **L1223** [技术债务]: parametrize over timezone?

🟡 **L1349** [技术债务]: (GH#55564): as_unit will be unnecessary

🟡 **L1374** [技术债务]: redundant with test_dt64arr_add_sub_DateOffset?  that includes

🟡 **L1472** [技术债务]: (GH#55564): as_unit will be unnecessary

🟡 **L1623** [技术债务]: box + de-duplicate

🟡 **L1803** [技术债务]: This next block of tests came from tests.series.test_operators,

🟡 **L2120** [技术债务]: A couple other tests belong in this section.  Move them in

🟡 **L2181** [技术债务]: Most of this block is moved from series or frame tests, needs

🟡 **L2449** [技术债务]: Can we default to the ser unit?


### venv/lib/python3.13/site-packages/pandas/tests/arithmetic/test_timedelta64.py

🟡 **L171** [技术债务]: All of these need to be parametrized over box

🟡 **L256** [技术债务]: better name

🟡 **L500** [技术债务]: don't leave commented-out

🟡 **L519** [技术债务]: Needs more informative name, probably split up into

🟡 **L669** [技术债务]: parametrize over boxes

🟡 **L695** [技术债务]: Make raised error message more informative and test

🟡 **L743** [技术债务]: moved from tests.indexes.timedeltas.test_arithmetic; needs

🟡 **L839** [技术债务]: moved from tests.series.test_operators, needs splitting, cleanup,

🟡 **L1141** [技术债务]: get inplace ops into assert_invalid_addsub_type

🟡 **L1516** [技术债务]: Put Series/DataFrame in others?

🟡 **L1819** [技术债务]: operations with timedelta-like arrays, numeric arrays,

🟡 **L1835** [技术债务]: making expected be object here a result of DataFrame.__divmod__

🟡 **L2074** [技术债务]: Should we be parametrizing over types for `ser` too?

🟡 **L2094** [技术债务]: Should we be parametrizing over types for `ser` too?


### venv/lib/python3.13/site-packages/pandas/tests/arithmetic/test_numeric.py

🟡 **L50** [技术债务]: add more  dtypes here

🟡 **L102** [技术债务]: remove this kludge once mypy stops giving false positives here

🟡 **L223** [技术债务]: also test Tick objects;

🟡 **L827** [技术债务]: This came from series.test.test_operators, needs cleanup

🟡 **L844** [技术债务]: this came from tests.series.test_analytics, needs cleanup and

🟡 **L927** [技术债务]: This came from series.test.test_operators, needs cleanup

🟡 **L961** [技术债务]: This came from series.test.test_operators, needs cleanup

🟡 **L993** [技术债务]: taken from tests.frame.test_operators, needs cleanup

🟡 **L1125** [技术债务]: add more dtypes

🟡 **L1141** [技术债务]: add more dtypes

🟡 **L1185** [技术债务]: add more dtypes

🟡 **L1239** [技术债务]: moved from tests.series.test_operators; needs cleanup

🟡 **L1340** [技术债务]: divmod?

🟡 **L1412** [技术债务]: add more dtypes


### venv/lib/python3.13/site-packages/pandas/tests/arithmetic/test_object.py

🟡 **L96** [技术债务]: parametrize

🟡 **L197** [技术债务]: Moved from tests.series.test_operators; needs cleanup

🟡 **L208** [技术债务]: parametrize over box

🟡 **L228** [技术债务]: cleanup & parametrize over box

🟡 **L280** [技术债务]: cleanup & parametrize over box


### venv/lib/python3.13/site-packages/pandas/tests/generic/test_finalize.py

🟡 **L13** [技术债务]: :

🟡 **L58** [技术债务]: mul, div, etc.

🟡 **L113** [技术债务]: div, mul, etc.


### venv/lib/python3.13/site-packages/pandas/tests/generic/test_duplicate_labels.py

🟡 **L51** [技术债务]: frame

🟡 **L205** [技术债务]: :


### venv/lib/python3.13/site-packages/pandas/tests/tslibs/test_array_to_datetime.py

🟡 **L27** [技术债务]: tests that include tzs, ints


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_chaining_and_caching.py

🟡 **L561** [技术债务]: (ArrayManager) fast_xs with array-like scalars is not yet working


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_at.py

🟡 **L166** [技术债务]: De-duplicate/parametrize


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_iloc.py

🟡 **L571** [技术债务]: GH#27620 this test used to compare iloc against ix; check if this

🟡 **L1252** [技术债务]: make an extension interface test for this?


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_loc.py

🟡 **L152** [技术债务]: test something?

🟡 **L443** [技术债务]: test something here?

🟡 **L1546** [技术债务]: (ArrayManager) we are still overwriting columns

🟡 **L1561** [技术债务]: (ArrayManager) we are still overwriting columns

🟡 **L1745** [技术债务]: should it?  unambiguous when lengths dont match?

🟡 **L2011** [技术债务]: should we have name="bar"?

🟡 **L2188** [技术债务]: using a tuple key breaks here in many cases

🟡 **L2691** [技术债务]: (ArrayManager) rewrite not using .values

🟡 **L3020** [技术债务]: i think this actually should drop levels


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_indexing.py

🟡 **L911** [技术债务]: (EA2D): we can make this no-copy in tz-naive case too

🟡 **L939** [技术债务]: (EA2D): we can make this no-copy in tz-naive case too

🟡 **L1067** [技术债务]: For object dtype this happens as well, but should we rather preserve

🟡 **L1122** [技术债务]: this only happens in case of ndarray, should we make this consistent


### venv/lib/python3.13/site-packages/pandas/tests/indexing/test_coercion.py

🟡 **L351** [技术债务]: ATM inserting '2012-01-01 00:00:00' when we have obj.freq=="M"


### venv/lib/python3.13/site-packages/pandas/tests/base/test_value_counts.py

🟡 **L50** [技术债务]: (GH#32514): Order of entries with the same count is inconsistent

🟡 **L93** [技术债务]: (GH#32514):

🟡 **L110** [技术债务]: (GH#32514):


### venv/lib/python3.13/site-packages/pandas/tests/base/test_misc.py

🟡 **L155** [技术债务]: Should Series cases also raise? Looks like they use numpy


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_common.py

🟡 **L169** [技术债务]: belongs in series arithmetic tests?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_any_index.py

🟡 **L50** [技术债务]: could work that into the 'exact="equiv"'?

🟡 **L51** [技术债务]: doesn't belong in this file anymore!


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_indexing.py

🟡 **L158** [技术债务]: do we want this to raise?

🟡 **L208** [技术债务]: make these more consistent?

🟡 **L226** [技术债务]: make these more consistent?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_setops.py

🟡 **L197** [技术债务]: pin down desired dtype; do we want it to be commutative?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_base.py

🟡 **L57** [技术债务]: a bunch of scattered tests check this deprecation is enforced.

🟡 **L440** [技术债务]: should right.asof(left[0]) also raise?

🟡 **L714** [技术债务]: case with complex dtype?

🟡 **L1541** [技术债务]: also this op right now produces FutureWarning from numpy


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_numpy_compat.py

🟡 **L155** [技术债务]: overlap with tests.series.test_ufunc.test_reductions

🟡 **L170** [技术债务]: do we have cases both with and without NAs?


### venv/lib/python3.13/site-packages/pandas/tests/series/methods/test_diff.py

🟡 **L14** [技术债务]: (__array_function__): could make np.diff return a Series


### venv/lib/python3.13/site-packages/pandas/tests/series/methods/test_astype.py

🟡 **L403** [技术债务]: same for EA float/uint dtypes, signed integers?


### venv/lib/python3.13/site-packages/pandas/tests/series/methods/test_align.py

🟡 **L210** [技术债务]: assert something?


### venv/lib/python3.13/site-packages/pandas/tests/series/methods/test_clip.py

🟡 **L73** [技术债务]: avoid this warning here?  seems like we should never be upcasting


### venv/lib/python3.13/site-packages/pandas/tests/series/indexing/test_setitem.py

🟡 **L437** [技术债务]: ser.where(~mask, alt) unnecessarily upcasts to int64

🟡 **L549** [技术债务]: GH#56010

🟡 **L942** [技术债务]: maybe go to float64 since we are changing the _whole_ Series?

🟡 **L977** [技术债务]: could also try np.full((1,), td)


### venv/lib/python3.13/site-packages/pandas/tests/reshape/concat/test_append.py

🟡 **L370** [技术债务]: expected used to be `other.astype(object)` which is a more


### venv/lib/python3.13/site-packages/pandas/tests/reshape/concat/test_concat.py

🟡 **L803** [技术债务]: what exact behaviour do we want for integer eventually?

🟡 **L819** [技术债务]: what exact behaviour do we want for integer eventually?


### venv/lib/python3.13/site-packages/pandas/tests/reshape/concat/test_datetimes.py

🟡 **L233** [技术债务]: setting nan here is to keep the test passing as we


### venv/lib/python3.13/site-packages/pandas/tests/reshape/merge/test_merge_asof.py

🟡 **L3141** [技术债务]: (GH#32306): may be relevant to the expected behavior here.


### venv/lib/python3.13/site-packages/pandas/tests/reshape/merge/test_merge.py

🟡 **L571** [技术债务]: should the next loop be un-indented? doing so breaks this test

🟡 **L735** [技术债务]: (ArrayManager) decide on exact casting rules in concat

🟡 **L1484** [技术债务]: check_names on merge?

🟡 **L2384** [技术债务]: might reconsider current raise behaviour, see issue 24782


### venv/lib/python3.13/site-packages/pandas/tests/extension/json/test_json.py

🟡 **L185** [技术债务]: (EA.factorize): see if _values_for_factorize allows this.


### venv/lib/python3.13/site-packages/pandas/tests/extension/json/array.py

🟡 **L263** [技术债务]: Use a regular dict. See _NDFrameIndexer._setitem_with_indexer


### venv/lib/python3.13/site-packages/pandas/tests/extension/list/array.py

🟡 **L130** [技术债务]: Use a regular dict. See _NDFrameIndexer._setitem_with_indexer


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/missing.py

🟡 **L30** [技术债务]: GH 57739


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/methods.py

🟡 **L70** [技术债务]: avoid special-casing

🟡 **L75** [技术债务]: avoid special-casing

🟡 **L78** [技术债务]: (GH#44692): avoid special-casing


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/reduce.py

🟡 **L86** [技术债务]: the message being checked here isn't actually checking anything

🟡 **L105** [技术债务]: the message being checked here isn't actually checking anything

🟡 **L134** [技术债务]: (3.0): remove BaseNoReduceTests, BaseNumericReduceTests,


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/setitem.py

🟡 **L220** [技术债务]: (xfail) this raises KeyError about labels not found (it tries label-based)

🟡 **L420** [技术债务]: (ArrayManager): this should work there too


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/accumulate.py

🟡 **L39** [技术债务]: require TypeError for things that will _never_ work?


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/getitem.py

🟡 **L124** [技术债务]: box over scalar, [scalar], (scalar,)?

🟡 **L272** [技术债务]: this raises KeyError about labels not found (it tries label-based)


### venv/lib/python3.13/site-packages/pandas/tests/extension/base/dim2.py

🟡 **L31** [技术债务]: is there a less hacky way of checking this?


### venv/lib/python3.13/site-packages/pandas/tests/io/formats/test_to_string.py

🟡 **L391** [技术债务]: assert that these match??

🟡 **L836** [技术债务]: don't leave commented-out

🟡 **L853** [技术债务]: split or simplify this test?


### venv/lib/python3.13/site-packages/pandas/tests/io/formats/test_to_html.py

🟡 **L373** [技术债务]: split this test


### venv/lib/python3.13/site-packages/pandas/tests/io/formats/test_format.py

🟡 **L1253** [技术债务]: don't leave commented-out


### venv/lib/python3.13/site-packages/pandas/tests/io/excel/test_readers.py

🟡 **L248** [技术债务]: add index to xls file)

🟡 **L269** [技术债务]: add index to xls, read xls ignores index name ?

🟡 **L286** [技术债务]: add index to xls file

🟡 **L444** [技术债务]: add index to file


### venv/lib/python3.13/site-packages/pandas/tests/io/excel/test_style.py

🟡 **L29** [技术债务]: should find a better way to check equality


### venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_parse_dates.py

🟡 **L1015** [技术债务]: make unit check more specific

🟡 **L1354** [技术债务]: parse dates directly in pyarrow, see

🟡 **L2312** [技术债务]: make unit check more specific


### venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_encoding.py

🟡 **L190** [技术债务]: this is bad!


### venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_na_values.py

🟡 **L686** [技术债务]: this test isn't about the na_values keyword, it is about the empty entries


### venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_quoting.py

🟡 **L28** [技术债务]: write a regex that works with all new possitibilities here


### venv/lib/python3.13/site-packages/pandas/tests/io/json/test_json_table_schema.py

🟡 **L212** [技术债务]: datedate.date? datetime.time?

🟡 **L219** [技术债务]: (GH#14904) flesh out dtypes?


### venv/lib/python3.13/site-packages/pandas/tests/io/json/test_pandas.py

🟡 **L177** [技术债务]: a to_epoch method would also solve; see GH 14772

🟡 **L293** [技术债务]: handle consistently across orients

🟡 **L1008** [技术债务]: check_dtype/check_index_type should be removable

🟡 **L1433** [技术债务]: there is a near-identical test for pytables; can we share?

🟡 **L1491** [技术债务]: We are casting to string which coerces None to NaN before casting back

🟡 **L1708** [技术债务]: the below have separate encoding procedures


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_put.py

🟡 **L302** [技术债务]: (infer_string) make this work for string dtype


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_select.py

🟡 **L892** [技术债务]: 2021-01-20 this is failing with freq None vs 4B on some builds


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_append.py

🟡 **L254** [技术债务]: Test is incorrect when not using_infer_string.

🟡 **L604** [技术债务]: 2020-05-07 freq check randomly fails in the CI

🟡 **L633** [技术债务]: 2020-12-07 intermittent build failures here with freq of

🟡 **L742** [技术债务]: (ArrayManager) currently we rely on falling back to BlockManager, but


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_round_trip.py

🟡 **L438** [技术债务]: (infer_string) make this work for string dtype


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_store.py

🟡 **L745** [技术债务]: 2021-01-18 on some (mostly windows) builds we get freq=None


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_read.py

🟡 **L232** [技术债务]: (infer_string) make this work for string dtype


### venv/lib/python3.13/site-packages/pandas/tests/io/pytables/test_file_handling.py

🟡 **L366** [技术债务]: (3.0): once Categorical replace deprecation is enforced,


### venv/lib/python3.13/site-packages/pandas/tests/io/parser/common/test_common_basic.py

🟡 **L96** [技术债务]: make unit check more specific

🟡 **L200** [技术债务]: make unit check more specific


### venv/lib/python3.13/site-packages/pandas/tests/tseries/offsets/test_year.py

🟡 **L330** [技术债务]: (cython3): "arg: datetime" annotation will impose


### venv/lib/python3.13/site-packages/pandas/tests/tseries/offsets/test_business_hour.py

🟡 **L986** [技术债务]: (GH#55564): as_unit will be unnecessary


### venv/lib/python3.13/site-packages/pandas/tests/tseries/offsets/test_offsets.py

🟡 **L573** [技术债务]: belongs in arithmetic tests?

🟡 **L590** [技术债务]: (GH#55564): as_unit will be unnecessary


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_shift.py

🟡 **L469** [技术债务]: (ArrayManager) axis=1 support


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_combine_first.py

🟡 **L212** [技术债务]: this must be int64

🟡 **L218** [技术债务]: this must be datetime64

🟡 **L220** [技术债务]: this must be int64

🟡 **L291** [技术债务]: parametrizing over unit breaks on non-nano


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_quantile.py

🟡 **L796** [技术债务]: tests for axis=1?

🟡 **L797** [技术债务]: empty case?


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_update.py

🟡 **L186** [技术债务]: (CoW-warn) better warning message


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_astype.py

🟡 **L129** [技术债务]: (wesm): verification?

🟡 **L418** [技术债务]: this is ValueError while for DatetimeArray it is TypeError;


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_rename.py

🟡 **L388** [技术债务]: can we construct this without merge?


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_fillna.py

🟡 **L33** [技术债务]: (CoW-warn) better warning message

🟡 **L44** [技术债务]: what's the expected/desired behavior with CoW?

🟡 **L100** [技术债务]: make stronger assertion here, GH 25640


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_sort_index.py

🟡 **L596** [技术债务]: better name, de-duplicate with test_sort_index_level above


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_rank.py

🟡 **L504** [技术债务]: nullable string[python] should also return nullable Int64


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_replace.py

🟡 **L751** [技术债务]: what is this even testing?


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_clip.py

🟡 **L159** [技术债务]: avoid this warning here?  seems like we should never be upcasting


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_tz_convert.py

🟡 **L93** [技术债务]: untested


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_select_dtypes.py

🟡 **L317** [技术债务]: warn

🟡 **L323** [技术债务]: warn


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_asfreq.py

🟡 **L154** [技术债务]: actually check that this worked.


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_interpolate.py

🟡 **L336** [技术债务]: assert something?

🟡 **L490** [技术债务]: (ArrayManager) support axis=1


### venv/lib/python3.13/site-packages/pandas/tests/frame/methods/test_to_csv.py

🟡 **L547** [技术债务]: to_csv drops column name

🟡 **L566** [技术债务]: to_csv drops column name


### venv/lib/python3.13/site-packages/pandas/tests/frame/indexing/test_xs.py

🟡 **L153** [技术债务]: more descriptive name

🟡 **L423** [技术债务]: the "split" path behaves differently here as with single block

🟡 **L434** [技术债务]: iloc does not update the array inplace using


### venv/lib/python3.13/site-packages/pandas/tests/frame/indexing/test_setitem.py

🟡 **L726** [技术债务]: (ArrayManager) set column with 2d column array, see #44788

🟡 **L1085** [技术债务]: (ArrayManager) rewrite not using .values

🟡 **L1424** [技术债务]: (COW): should this warn?


### venv/lib/python3.13/site-packages/pandas/tests/frame/indexing/test_indexing.py

🟡 **L644** [技术债务]: (ArrayManager) rewrite not using .values

🟡 **L684** [技术债务]: (ArrayManager) rewrite not using .values

🟡 **L1025** [技术债务]: rename?  remove?


### venv/lib/python3.13/site-packages/pandas/tests/frame/indexing/test_coercion.py

🟡 **L45** [技术债务]: i think this isn't about MultiIndex and could be done with iloc?

🟡 **L166** [技术债务]: OP in GH#12499 used np.datetim64("NaT") instead of pd.NaT,


### venv/lib/python3.13/site-packages/pandas/tests/frame/indexing/test_where.py

🟡 **L727** [技术债务]: ideally we would get Int64 instead of object


### venv/lib/python3.13/site-packages/pandas/tests/dtypes/cast/test_downcast.py

🟡 **L46** [技术债务]: similar for dt64, dt64tz, Period, Interval?


### venv/lib/python3.13/site-packages/pandas/tests/groupby/methods/test_value_counts.py

🟡 **L427** [技术债务]: (nullable) also string[python] should return nullable dtypes


### venv/lib/python3.13/site-packages/pandas/tests/groupby/methods/test_quantile.py

🟡 **L65** [技术债务]: (non-nano): this should be unnecessary once array_to_datetime


### venv/lib/python3.13/site-packages/pandas/tests/groupby/aggregate/test_aggregate.py

🟡 **L1356** [技术债务]: agg should raise for functions that don't aggregate


### venv/lib/python3.13/site-packages/pandas/tests/groupby/aggregate/test_other.py

🟡 **L444** [技术债务]: the original version of this test called `gb.agg(sum)`


### venv/lib/python3.13/site-packages/pandas/tests/groupby/transform/test_transform.py

🟡 **L872** [技术债务]: create xfail condition given other params


### venv/lib/python3.13/site-packages/pandas/tests/groupby/transform/test_numba.py

🟡 **L149** [技术债务]: Test more than just reductions (e.g. actually test transformations once we have


### venv/lib/python3.13/site-packages/pandas/tests/plotting/frame/test_frame.py

🟡 **L343** [技术债务]: add MultiIndex test

🟡 **L1573** [技术债务]: need better way to test. This just does existence.


### venv/lib/python3.13/site-packages/pandas/tests/arrays/string_/test_string.py

🟡 **L877** [技术债务]: we should infer int64 dtype here?

🟡 **L886** [技术债务]: ArrowStringArray should also preserve the class / dtype


### venv/lib/python3.13/site-packages/pandas/tests/arrays/masked/test_indexing.py

🟡 **L22** [技术债务]: don't leave commented-out

🟡 **L33** [技术债务]: so, so many other variants of this...


### venv/lib/python3.13/site-packages/pandas/tests/arrays/masked/test_arithmetic.py

🟡 **L57** [技术债务]: also add len-1 array (np.array([scalar], dtype=data.dtype.numpy_dtype))


### venv/lib/python3.13/site-packages/pandas/tests/arrays/categorical/test_analytics.py

🟡 **L47** [技术债务]: raises if we pass axis=0  (on Index and Categorical, not Series)


### venv/lib/python3.13/site-packages/pandas/tests/arrays/categorical/test_indexing.py

🟡 **L374** [技术债务]: (Categorical): identify other places where this may be


### venv/lib/python3.13/site-packages/pandas/tests/arrays/boolean/test_logical.py

🟡 **L123** [技术债务]: test True & False


### venv/lib/python3.13/site-packages/pandas/tests/arrays/boolean/test_construction.py

🟡 **L155** [技术债务]: this is currently not public API


### venv/lib/python3.13/site-packages/pandas/tests/arrays/boolean/test_arithmetic.py

🟡 **L122** [技术债务]: (extension) numpy's mul with object array sees booleans as numbers


### venv/lib/python3.13/site-packages/pandas/tests/arrays/integer/test_arithmetic.py

🟡 **L196** [技术债务]: doing this fillna to keep tests passing as we make

🟡 **L212** [技术债务]: test unsigned overflow

🟡 **L337** [技术债务]: desired behavior when operating with boolean?  defer?


### venv/lib/python3.13/site-packages/pandas/tests/arrays/floating/test_construction.py

🟡 **L172** [技术债务]: can we specify "floating" in general?


### venv/lib/python3.13/site-packages/pandas/tests/arrays/floating/test_arithmetic.py

🟡 **L39** [技术债务]: pending NA/NaN discussion

🟡 **L67** [技术债务]: np.nan should be converted to pd.NA / missing before operation?


### venv/lib/python3.13/site-packages/pandas/tests/arrays/sparse/test_reductions.py

🟡 **L265** [技术债务]: pin down whether we wrap datetime64("NaT")


### venv/lib/python3.13/site-packages/pandas/tests/arrays/sparse/test_constructors.py

🟡 **L106** [技术债务]: actionable?


### venv/lib/python3.13/site-packages/pandas/tests/arrays/sparse/test_indexing.py

🟡 **L208** [技术债务]: actionable?

🟡 **L243** [技术债务]: actionable?


### venv/lib/python3.13/site-packages/pandas/tests/indexing/interval/test_interval_new.py

🟡 **L171** [技术债务]: KeyError is the appropriate error?


### venv/lib/python3.13/site-packages/pandas/tests/indexing/multiindex/test_setitem.py

🟡 **L129** [技术债务]: (ArrayManager) df.loc["bar"] *= 2 doesn't raise an error but results in


### venv/lib/python3.13/site-packages/pandas/tests/indexing/multiindex/test_loc.py

🟡 **L836** [技术债务]: standardize return type for MultiIndex.get_loc


### venv/lib/python3.13/site-packages/pandas/tests/indexing/multiindex/test_partial.py

🟡 **L121** [技术债务]: (ArrayManager) rewrite test to not use .values


### venv/lib/python3.13/site-packages/pandas/tests/scalar/timedelta/test_constructors.py

🟡 **L141** [技术债务]: (2.0): the desired output dtype may have non-nano resolution


### venv/lib/python3.13/site-packages/pandas/tests/scalar/timedelta/test_timedelta.py

🟡 **L401** [技术债务]: this is a test of to_timedelta string parsing

🟡 **L407** [技术债务]: this is a test of to_timedelta returning NaT


### venv/lib/python3.13/site-packages/pandas/tests/scalar/period/test_period.py

🟡 **L88** [技术债务]: raise in the future an error when passing lowercase freq


### venv/lib/python3.13/site-packages/pandas/tests/scalar/timestamp/test_constructors.py

🟡 **L322** [技术债务]: if we passed microsecond with a keyword we would mess up


### venv/lib/python3.13/site-packages/pandas/tests/indexes/interval/test_indexing.py

🟡 **L369** [技术债务]: with mismatched resolution get_indexer currently raises;

🟡 **L435** [技术债务]: we may also want to test get_indexer for the case when


### venv/lib/python3.13/site-packages/pandas/tests/indexes/interval/test_formats.py

🟡 **L18** [技术债务]: this is a test for DataFrame/Series, not IntervalIndex


### venv/lib/python3.13/site-packages/pandas/tests/indexes/interval/test_setops.py

🟡 **L184** [技术债务]: standardize return type of non-union setops type(self vs other)


### venv/lib/python3.13/site-packages/pandas/tests/indexes/multi/test_reshape.py

🟡 **L69** [技术债务]: data types changes to float because


### venv/lib/python3.13/site-packages/pandas/tests/indexes/multi/test_analytics.py

🟡 **L76** [技术债务]: reshape


### venv/lib/python3.13/site-packages/pandas/tests/indexes/multi/test_indexing.py

🟡 **L85** [技术债务]: Try creating a UnicodeDecodeError in exception message

🟡 **L744** [技术债务]: de-duplicate with test_get_loc_duplicates above?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/multi/test_setops.py

🟡 **L233** [技术债务]: this is raising in constructing a Categorical when calling


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/test_indexing.py

🟡 **L480** [技术债务]: This method came from test_period; de-dup with version above


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/test_formats.py

🟡 **L115** [技术债务]: These are Series.__repr__ tests


### venv/lib/python3.13/site-packages/pandas/tests/indexes/numeric/test_numeric.py

🟡 **L535** [技术债务]: we could plausibly try to infer down to int16 here


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_constructors.py

🟡 **L85** [技术债务]: better place for tests shared by DTI/TDI?

🟡 **L999** [技术债务]: The Timestamp constructor here behaves differently than all


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_date_range.py

🟡 **L1303** [技术债务]: give a more useful or informative message?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_indexing.py

🟡 **L294** [技术债务]: This method came from test_datetime; de-dup with version above


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_formats.py

🟡 **L189** [技术债务]: this is a Series.__repr__ test


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_setops.py

🟡 **L43** [技术债务]: moved from test_datetimelike; dedup with version below

🟡 **L204** [技术债务]: moved from test_datetimelike; de-duplicate with version below


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/test_datetime.py

🟡 **L73** [技术债务]: belongs in frame groupby tests?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/timedeltas/test_scalar_compat.py

🟡 **L98** [技术债务]: de-duplicate with test_tdi_round


### venv/lib/python3.13/site-packages/pandas/tests/indexes/timedeltas/test_formats.py

🟡 **L54** [技术债务]: this is a Series.__repr__ test


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimelike_/test_equals.py

🟡 **L56** [技术债务]: de-duplicate with other test_equals2 methods


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/methods/test_to_timestamp.py

🟡 **L30** [技术债务]: can we get the freq to round-trip?


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/methods/test_astype.py

🟡 **L83** [技术债务]: de-duplicate this version (from test_ops) with the one above


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/methods/test_insert.py

🟡 **L180** [技术债务]: also changes DataFrame.__setitem__ with expansion

🟡 **L201** [技术债务]: also changes DataFrame.__setitem__ with expansion


### venv/lib/python3.13/site-packages/pandas/tests/indexes/datetimes/methods/test_delete.py

🟡 **L117** [技术债务]: belongs in Series.drop tests?


### venv/lib/python3.13/site-packages/pandas/plotting/_matplotlib/misc.py

🟡 **L300** [技术债务]: is the failure mentioned below still relevant?


### venv/lib/python3.13/site-packages/pandas/plotting/_matplotlib/converter.py

🟡 **L823** [技术债务]: Check the following : is it really info['fmt'] ?

🟡 **L1124** [技术债务]: (non-nano): this looks like it assumes ns


### venv/lib/python3.13/site-packages/pandas/plotting/_matplotlib/core.py

🟡 **L182** [技术债务]: Might deprecate `column` argument in future PR (#28373)

🟡 **L252** [技术债务]: deprecate fig keyword as it is ignored, not passed in tests

🟡 **L394** [技术债务]: also accept indices instead of just names?

🟡 **L531** [技术债务]: use Matplotlib public API when available

🟡 **L533** [技术债务]: #54485

🟡 **L537** [技术债务]: #54485

🟡 **L559** [技术债务]: can we annotate this as both a Sequence[Axes] and ndarray[object]?

🟡 **L685** [技术债务]: change after solving issue 27881

🟡 **L935** [技术债务]: be stricter about x?

🟡 **L941** [技术债务]: why do we need to do to_timestamp() here but not other

🟡 **L1100** [技术债务]: tighter typing for first return?

🟡 **L1420** [技术债务]: warn that we are ignoring self.norm if user specified it?

🟡 **L1564** [技术债务]: GH28021, should find a way to change view limit on xaxis

🟡 **L1604** [技术债务]: #54485

🟡 **L1609** [技术债务]: #54485

🟡 **L1626** [技术债务]: #54485

🟡 **L1629** [技术债务]: #54485

🟡 **L1631** [技术债务]: #54485

🟡 **L1633** [技术债务]: #54485

🟡 **L1648** [技术债务]: #54485

🟡 **L1654** [技术债务]: #54485

🟡 **L1672** [技术债务]: #54485

🟡 **L1675** [技术债务]: #54485

🟡 **L1773** [技术债务]: #54485

🟡 **L1776** [技术债务]: #54485

🟡 **L2077** [技术债务]: warn if color is passed and ignored?


### venv/lib/python3.13/site-packages/pandas/plotting/_matplotlib/timeseries.py

🟡 **L1** [技术债务]: Use the fact that axis can have units to simplify the process

🟡 **L139** [技术债务]: #54485

🟡 **L152** [技术债务]: #54485

🟡 **L170** [技术债务]: #54485

🟡 **L173** [技术债务]: #54485

🟡 **L176** [技术债务]: #54485

🟡 **L249** [技术债务]: hack this for 0.10.1, creating more technical debt...sigh

🟡 **L301** [技术债务]: need to find an alternative to this before the deprecation


### venv/lib/python3.13/site-packages/pandas/api/typing/__init__.py

🟡 **L29** [技术债务]: Can't import Styler without importing jinja2


### venv/lib/python3.13/site-packages/dateutil/zoneinfo/__init__.py

🟡 **L25** [技术债务]: switch to FileNotFoundError?

🟡 **L76** [技术债务]: Remove after deprecation period.


### venv/lib/python3.13/site-packages/dateutil/parser/_parser.py

🟡 **L55** [技术债务]: pandas.core.tools.datetimes imports this explicitly.  Might be worth

🟡 **L265** [技术债务]: "Tues"

🟡 **L267** [技术债务]: "Thurs"

🟡 **L272** [技术债务]: "Febr"

🟡 **L291** [技术债务]: ERA = ["AD", "BC", "CE", "BCE", "Stardate",

🟡 **L777** [技术债务]: not hit in tests

🟡 **L815** [技术债务]: check that l[i + 1] is integer?

🟡 **L823** [技术债务]: Check that l[i+3] is minute-like?

🟡 **L910** [技术债务]: Check if res attributes already set.

🟡 **L934** [技术债务]: checking that hour/minute/second are not

🟡 **L941** [技术债务]: try/except for this?

🟡 **L1032** [技术债务]: Are we sure this is the right condition here?

🟡 **L1100** [技术债务]: Every usage of this function sets res.second to the return

🟡 **L1112** [技术债务]: Is this going to admit a lot of false-positives for when we


### venv/lib/python3.13/site-packages/_pytest/config/argparsing.py

🟡 **L404** [技术债务]: (py313): Replace with `exit_on_error=False`. Note that while it


### venv/lib/python3.13/site-packages/_pytest/mark/structures.py

🟡 **L543** [技术债务]: (pytest10): Change to below after PARAMETRIZE_NON_COLLECTION_ITERABLE deprecation.


### venv/lib/python3.13/site-packages/_pytest/assertion/rewrite.py

🟡 **L858** [技术债务]: This assert should not be needed.


### venv/lib/python3.13/site-packages/pyarrow/tests/test_convert_builtin.py

🟡 **L688** [技术债务]: (wesm): see ARROW-5645

🟡 **L1914** [技术债务]: (kszucs): ARROW-9997


### venv/lib/python3.13/site-packages/pyarrow/tests/test_acero.py

🟡 **L257** [技术债务]: test with kernel that matches number of arguments (arity) -> avoid segfault


### venv/lib/python3.13/site-packages/pyarrow/tests/test_gandiva.py

🟡 **L85** [技术债务]: Add .evaluate function which can take Tables instead of


### venv/lib/python3.13/site-packages/pyarrow/tests/strategies.py

🟡 **L340** [技术债务]: (kszucs): properly limit the precision


### venv/lib/python3.13/site-packages/pyarrow/tests/test_array.py

🟡 **L4402** [技术债务]: support DLPack for CUDA


### venv/lib/python3.13/site-packages/pyarrow/tests/test_schema.py

🟡 **L85** [技术债务]: needs pandas conversion


### venv/lib/python3.13/site-packages/pyarrow/tests/test_jvm.py

🟡 **L155** [技术债务]: (ARROW-2609): complex types that have children

🟡 **L164** [技术债务]: DictionaryType requires a vector in the type

🟡 **L175** [技术债务]: This needs to be set for complex types

🟡 **L216** [技术债务]: (ARROW-2605): These types miss a conversion from pure Python objects

🟡 **L223** [技术债务]: (ARROW-2606): pa.decimal128(19, 4)

🟡 **L256** [技术债务]: null

🟡 **L306** [技术债务]: float16

🟡 **L343** [技术债务]: (ARROW-2605): These types miss a conversion from pure Python objects

🟡 **L360** [技术债务]: (ARROW-2606): pa.decimal128(19, 4)

🟡 **L379** [技术债务]: This needs to be set for complex types

🟡 **L418** [技术债务]: (ARROW-2607)


### venv/lib/python3.13/site-packages/pyarrow/tests/test_fs.py

🟡 **L957** [技术债务]: (GH-40025): Stop skipping this test

🟡 **L981** [技术债务]: (GH-40025): Stop skipping this test

🟡 **L1136** [技术债务]: (GH-40026): Stop skipping this test


### venv/lib/python3.13/site-packages/pyarrow/tests/test_dataset.py

🟡 **L621** [技术债务]: (ARROW-18293) we should be able to use the proxy memory pool for

🟡 **L3181** [技术债务]: (bkietz) reintroduce factory.children property

🟡 **L4009** [技术债务]: (bkietz) on Windows this results in FileNotFoundErrors.

🟡 **L4119** [技术债务]: (GH-34884) partitioning attribute not preserved in pickling

🟡 **L4147** [技术债务]: is this expected?


### venv/lib/python3.13/site-packages/pyarrow/tests/test_cuda.py

🟡 **L38** [技术债务]: enable ppc64 when Arrow C++ supports IPC in ppc64 systems:


### venv/lib/python3.13/site-packages/pyarrow/tests/test_pandas.py

🟡 **L2424** [技术债务]: regression in pandas with numpy 1.25dev

🟡 **L2449** [技术债务]: regression in pandas with numpy 1.25dev

🟡 **L4484** [技术债务]: do we require handling of chunked arrays in the protocol?


### venv/lib/python3.13/site-packages/pyarrow/tests/test_compute.py

🟡 **L230** [技术债务]: remove the check under the if statement and the filterwarnings

🟡 **L2512** [技术债务]: (GH-48767): On Windows, std::chrono returns GMT offset


### venv/lib/python3.13/site-packages/pyarrow/tests/test_gdb.py

🟡 **L103** [技术债务]: add timeout?

🟡 **L641** [技术债务]: excessive escaping ('\\xff' vs. '\x00')


### venv/lib/python3.13/site-packages/pyarrow/parquet/core.py

🟡 **L746** [技术债务]: This will not handle prohibited characters in nested field names


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_basic.py

🟡 **L849** [技术债务]: remove astype casts once fastparquet supports pandas 3 StringDtype


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_metadata.py

🟡 **L218** [技术债务]: (kszucs) until parquet-cpp API doesn't expose HasDistinctCount


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_datetime.py

🟡 **L410** [技术债务]: after pyarrow allows coerce_timestamps='ns', tests like the


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/common.py

🟡 **L123** [技术债务]: (PARQUET-1015)


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_dataset.py

🟡 **L137** [技术债务]: (ARROW-3388): boolean columns are reconstructed as string

🟡 **L691** [技术债务]: (dataset) Dataset API skips bad files


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_data_types.py

🟡 **L509** [技术债务]: (wesm): handle chunked children


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_pandas.py

🟡 **L434** [技术债务]: regression in pandas


### venv/lib/python3.13/site-packages/pyarrow/tests/parquet/test_parquet_file.py

🟡 **L209** [技术债务]: Add categorical support

🟡 **L352** [技术债务]: add tests for is_distinct_count_exact == None and True


### venv/lib/python3.13/site-packages/openpyxl/drawing/colors.py

🟡 **L200** [技术债务]: add color transform options

🟡 **L221** [技术债务]: add color transform options


### venv/lib/python3.13/site-packages/openpyxl/formula/tokenizer.py

🟡 **L89** [技术债务]: this can probably be sped up using a regex to get to


### application/services/strategy_discovery_service.py

🟡 **L504** [技术债务]: 从 stock info 获取


### application/services/combo_strategy_backtest_service.py

🟡 **L317** [技术债务]: calculate from trades


### application/services/decision_evaluator.py

🟡 **L204** [技术债务]: 实际应该计算收益率、夏普比率等


### application/services/stock_screening_service.py

🟡 **L202** [技术债务]: 获取最新价格


### application/services/order_service.py

🟡 **L707** [技术债务]: 计算实际持仓天数

🟡 **L708** [技术债务]: 从信号 details 中提取

🟡 **L709** [技术债务]: 从信号 details 中提取


### application/services/simulation_service.py

🟡 **L318** [技术债务]: 这里应该调用实际的SimulationTrader执行交易


### application/services/smart_scheduler.py

🟡 **L310** [技术债务]: 这里需要一个任务函数注册表


### application/services/market_data_service.py

🟡 **L27** [技术债务]: Phase 3 future work - migrate methods to use provider_manager


### application/services/opponent_behavior_service.py

🟡 **L140** [技术债务]: 这里需要获取市场整体资金流向，暂时使用模拟逻辑

🟡 **L235** [技术债务]: 分析目标板块（需要按行业聚合资金流向）


### application/services/enhanced_risk_assessor.py

🟡 **L311** [技术债务]: 分析行业集中度、权重集中度等


### application/services/agent_scheduler_tool.py

🟡 **L427** [技术债务]: 这里可以通过WebSocket或其他方式通知Agent


### application/services/manipulation_detector.py

🟡 **L331** [技术债务]: 获取股票基本面数据（PE、PB等）

🟡 **L354** [技术债务]: 获取K线数据，判断是否高位+放量+涨幅收窄

🟡 **L559** [技术债务]: 获取实时价格


### application/services/dividend_service.py

🟡 **L31** [技术债务]: Phase 3 future work - migrate methods to use provider_manager


### application/services/sector_rotation_service.py

🟡 **L89** [技术债务]: 从行业映射表获取


### application/services/data_quality_service.py

🟡 **L202** [技术债务]: 保存报告到数据库


### application/services/pool_scanner_service.py

🟡 **L357** [技术债务]: 保存到 pool_scan_results 表


### application/services/registry_client.py

🟡 **L106** [技术债务]: 根据实际状态动态设置


### infrastructure/scheduler/signal_execution_job.py

🟡 **L87** [技术债务]: 集成订单创建逻辑


### infrastructure/jobs/verification_job.py

🟡 **L252** [技术债务]: 从实际数据读取


### infrastructure/jobs/weekly_report_job.py

🟡 **L261** [技术债务]: 更准确的止损统计


### infrastructure/quantlib/core/portfolio_calculator.py

🟡 **L15** [技术债务]: 重构配置系统

🟡 **L44** [技术债务]: 重构配置系统后从配置读取


### infrastructure/quantlib/adapters/factory.py

🟡 **L21** [技术债务]: 配置系统重构

🟡 **L42** [技术债务]: 配置系统重构后从配置读取


### domain/memory/distiller.py

🟡 **L79** [技术债务]: Consider moving to a proper repository method


### domain/strategies/strategy_factory.py

🟡 **L69** [技术债务]: 添加ML策略时在这里注册


### domain/strategies/strategy_274_ml.py

🟡 **L30** [技术债务]: 实际加载训练好的模型


### domain/legacy/legacy_order_adapter.py

🟡 **L57** [技术债务]: 注入 stock_repo


### domain/benchmarks/run_all_benchmarks.py

🟡 **L33** [技术债务]: Make injection mandatory after all callers are updated


### tools/analyze_todos.py

🟡 **L130** [立即修复]: /FIXME 清理计划\n\n")


### live_trading/backtest_v14_optimized.py

🟡 **L63** [立即修复]: 实现完整回测逻辑


### live_trading/simulation_broker.py

🟡 **L298** [立即修复]: 实现完整的可交易性检查


### scripts/refactor/classify_todos.py

🟡 **L21** [立即修复]: or FIXME

🟡 **L128** [立即修复]: /FIXME 清单", ""]


### venv/lib/python3.13/site-packages/aiohttp/web_urldispatcher.py

🟡 **L387** [立即修复]: implement all abstract methods


### venv/lib/python3.13/site-packages/aiohttp/client_reqrep.py

🟡 **L347** [立即修复]: Fix session=None in tests (see ClientRequest.__init__).

🟡 **L889** [立即修复]: session is None in tests only, need to fix tests


### venv/lib/python3.13/site-packages/sqlparse/keywords.py

🟡 **L51** [立即修复]: Spaces before period not implemented


### venv/lib/python3.13/site-packages/mpmath/math2.py

🟡 **L359** [立即修复]: could implement complex erf and erfc here. Need


### venv/lib/python3.13/site-packages/seaborn/_base.py

🟡 **L157** [立即修复]: this needs actual implementation

🟡 **L342** [立即修复]: this needs an actual implementation

🟡 **L1432** [立即修复]: implement formatter here; check that it returns strings?


### venv/lib/python3.13/site-packages/fsspec/asyn.py

🟡 **L368** [立即修复]: implement on_error


### venv/lib/python3.13/site-packages/markdown/htmlparser.py

🟡 **L158** [立即修复]: remove this when the bug is fixed in all supported Python versions.


### venv/lib/python3.13/site-packages/xgboost/_data_utils.py

🟡 **L332** [立即修复]: (jiamingy): Account for offset, need to find an implementation that returns


### venv/lib/python3.13/site-packages/torch/_torch_docs.py

🟡 **L5296** [立即修复]: Fix via https://github.com/pytorch/pytorch/issues/75798


### venv/lib/python3.13/site-packages/torch/__init__.py

🟡 **L1085** [立即修复]: fix their module from C++ side


### venv/lib/python3.13/site-packages/torch/_tensor_str.py

🟡 **L345** [立即修复]: Remove me when `masked_select` is implemented for FP8


### venv/lib/python3.13/site-packages/torch/functional.py

🟡 **L1905** [立即修复]: when https://github.com/pytorch/pytorch/issues/33782 is fixed


### venv/lib/python3.13/site-packages/torch/_lobpcg.py

🟡 **L993** [立即修复]: use torch.linalg.cholesky_solve once it is implemented


### venv/lib/python3.13/site-packages/torch/_utils.py

🟡 **L1167** [立即修复]: (pianpwk): remove the unbacked symbols check and fix AsyncTP pattern matching


### venv/lib/python3.13/site-packages/PIL/FpxImagePlugin.py

🟡 **L182** [立即修复]: the fill decoder is not implemented

🟡 **L220** [立即修复]: jpeg tables are tile dependent; the prefix


### venv/lib/python3.13/site-packages/PIL/ImageDraw.py

🟡 **L98** [立即修复]: fix Fill2 to properly support matte for I+F images


### venv/lib/python3.13/site-packages/requests/models.py

🟡 **L685** [立即修复]: can be fixed by flipping the conditionals


### venv/lib/python3.13/site-packages/httpx/_auth.py

🟡 **L267** [立即修复]: implement auth-int


### venv/lib/python3.13/site-packages/fastapi/applications.py

🟡 **L929** [立即修复]: remove when discarding the openapi_prefix parameter


### venv/lib/python3.13/site-packages/prometheus_client/values.py

🟡 **L129** [立即修复]: Implement exemplars for multiprocess mode.

🟡 **L138** [立即修复]: Implement exemplars for multiprocess mode.


### venv/lib/python3.13/site-packages/torchgen/model.py

🟡 **L1933** [立即修复]: implement a proper parser if this gets more ugly


### venv/lib/python3.13/site-packages/torchgen/gen_lazy_tensor.py

🟡 **L135** [立即修复]: (whc) add a check for shape inference functions that have meta kernels implement and should be retired.


### venv/lib/python3.13/site-packages/urllib3/connection.py

🟡 **L336** [立即修复]: Fix tunnel so it doesn't depend on self.sock state.

🟡 **L567** [立即修复]: should we implement it everywhere?


### venv/lib/python3.13/site-packages/asttokens/util.py

🟡 **L123** [立即修复]: Remove cast once https://github.com/python/typeshed/issues/7003 gets fixed


### venv/lib/python3.13/site-packages/setuptools/_static.py

🟡 **L41** [立即修复]: After deprecation period raise NotImplementedError instead of warning


### venv/lib/python3.13/site-packages/httpx2/_auth.py

🟡 **L251** [立即修复]: implement auth-int


### venv/lib/python3.13/site-packages/_pytest/terminal.py

🟡 **L1593** [立即修复]: Revisit after marks scope would be fixed.


### venv/lib/python3.13/site-packages/_pytest/capture.py

🟡 **L708** [立即修复]: This type error is real, need to fix.


### venv/lib/python3.13/site-packages/_pytest/fixtures.py

🟡 **L188** [立即修复]: Try to use FixtureFunctionDefinition instead of the marker

🟡 **L1719** [立即修复]: The order of the FixtureDefs list of each arg is significant,

🟡 **L1937** [立即修复]: Handle the case where the super-fixture is transitively

🟡 **L2259** [立即修复]: Fix this type ignore.


### venv/lib/python3.13/site-packages/pyarrow/jvm.py

🟡 **L244** [立即修复]: The following JVM types are not implemented:


### venv/lib/python3.13/site-packages/pyasn1/type/constraint.py

🟡 **L85** [立即修复]: fix possible comparison of set vs scalars here


### venv/lib/python3.13/site-packages/pyasn1/codec/ber/decoder.py

🟡 **L60** [立即修复]: Seems more like an NotImplementedError?

🟡 **L70** [立即修复]: Seems more like an NotImplementedError?


### venv/lib/python3.13/site-packages/networkx/algorithms/tree/branchings.py

🟡 **L11** [立即修复]: Implement method from Gabow, Galil, Spence and Tarjan:


### venv/lib/python3.13/site-packages/networkx/algorithms/connectivity/edge_kcomponents.py

🟡 **L314** [立即修复]: fix decor for classmethods


### venv/lib/python3.13/site-packages/river/compat/river_to_sklearn.py

🟡 **L232** [立即修复]: change to a ValueError when fixed


### venv/lib/python3.13/site-packages/river/utils/math.py

🟡 **L373** [立即修复]: try several log and exp implementations


### venv/lib/python3.13/site-packages/cvxpy/atoms/stats.py

🟡 **L64** [立即修复]: when sum_squares implements axis and keepdims uncomment:


### venv/lib/python3.13/site-packages/cvxpy/atoms/norm_inf.py

🟡 **L131** [立即修复]: (akshayka): Implement this.


### venv/lib/python3.13/site-packages/cvxpy/atoms/cumprod.py

🟡 **L79** [立即修复]: implement grad


### venv/lib/python3.13/site-packages/cvxpy/constraints/exponential.py

🟡 **L83** [立即修复]: (akshayka): The projection should be implemented directly.

🟡 **L224** [立即修复]: (akshayka): The projection should be implemented directly.

🟡 **L279** [立即修复]: implement me.

🟡 **L352** [立即修复]: implement me

🟡 **L396** [立即修复]: implement me.


### venv/lib/python3.13/site-packages/cvxpy/constraints/power.py

🟡 **L80** [立即修复]: The projection should be implemented directly.

🟡 **L260** [立即修复]: The projection should be implemented directly.


### venv/lib/python3.13/site-packages/cvxpy/transforms/suppfunc.py

🟡 **L72** [立即修复]: implement


### venv/lib/python3.13/site-packages/cvxpy/reductions/complex2real/complex2real.py

🟡 **L351** [立即修复]: implement dual variable recovery


### venv/lib/python3.13/site-packages/docker/utils/ports.py

🟡 **L60** [立即修复]: remove once fixed in Compose stable


### venv/lib/python3.13/site-packages/sympy/polys/heuristicgcd.py

🟡 **L124** [立即修复]: don't expose poly repr implementation details


### venv/lib/python3.13/site-packages/sympy/holonomic/holonomic.py

🟡 **L732** [立即修复]: Implement this case


### venv/lib/python3.13/site-packages/sympy/solvers/pde.py

🟡 **L175** [立即修复]: : 'best' hint should be implemented when adequate


### venv/lib/python3.13/site-packages/sympy/integrals/laplace.py

🟡 **L875** [立即修复]: not implemented yet, but also not important


### venv/lib/python3.13/site-packages/sympy/integrals/prde.py

🟡 **L822** [立即修复]: implement this

🟡 **L957** [立即修复]: This could be implemented more efficiently.


### venv/lib/python3.13/site-packages/sympy/sets/setexpr.py

🟡 **L84** [立即修复]: this could be implemented straight into `imageset`:


### venv/lib/python3.13/site-packages/sympy/stats/frv.py

🟡 **L460** [立即修复]: Implement the mechanism for handling queries for symbolic sized distributions.


### venv/lib/python3.13/site-packages/sympy/polys/domains/domain.py

🟡 **L450** [立即修复]: implement this in from_ methods


### venv/lib/python3.13/site-packages/sympy/polys/matrices/rref.py

🟡 **L256** [立即修复]: Add partial pivot support to the sparse implementations.


### venv/lib/python3.13/site-packages/sympy/polys/matrices/_dfm.py

🟡 **L660** [立即修复]: Implement similar algorithms for DDM and SDM.


### venv/lib/python3.13/site-packages/sympy/concrete/tests/test_sums_products.py

🟡 **L1043** [立即修复]: Implement matrix geometric series summation.


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_theanocode.py

🟡 **L172** [立即修复]: - this is currently not checked but should be implemented

🟡 **L599** [立即修复]: - implement


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_smtlib.py

🟡 **L216** [立即修复]: implement re-write, currently does '(+ x (* -1 y))' instead


### venv/lib/python3.13/site-packages/sympy/printing/tests/test_aesaracode.py

🟡 **L182** [立即修复]: - this is currently not checked but should be implemented

🟡 **L611** [立即修复]: - implement


### venv/lib/python3.13/site-packages/sympy/utilities/tests/test_pickling.py

🟡 **L382** [立即修复]: fix pickling of Options class (see GroebnerBasis._options)

🟡 **L438** [立即修复]: fix pickling of ModularInteger

🟡 **L444** [立即修复]: fix pickling of RealElement

🟡 **L448** [立即修复]: fix pickling of ComplexElement

🟡 **L457** [立即修复]: fix pickling of ModularInteger

🟡 **L472** [立即修复]: fix pickling of ModularInteger

🟡 **L489** [立即修复]: fix pickling of RealElement

🟡 **L493** [立即修复]: fix pickling of ComplexElement

🟡 **L635** [立即修复]: fix pickling of `symbols' flag


### venv/lib/python3.13/site-packages/sympy/integrals/tests/test_meijerint.py

🟡 **L278** [立即修复]: more indefinite integrals when struve functions etc are implemented


### venv/lib/python3.13/site-packages/sympy/assumptions/handlers/matrices.py

🟡 **L47** [立即修复]: implement sathandlers system for the matrices.

🟡 **L77** [立即修复]: implement sathandlers system for the matrices.

🟡 **L94** [立即修复]: implement sathandlers system for the matrices.


### venv/lib/python3.13/site-packages/sympy/plotting/backends/matplotlibbackend/matplotlib.py

🟡 **L304** [立即修复]: after fixing https://github.com/ipython/ipython/issues/1255


### venv/lib/python3.13/site-packages/sympy/functions/special/zeta_functions.py

🟡 **L179** [立即修复]: use minpoly instead of ad-hoc methods when issue 5888 is fixed


### venv/lib/python3.13/site-packages/sympy/functions/elementary/trigonometric.py

🟡 **L498** [立即修复]: , implement more if deep stuff here


### venv/lib/python3.13/site-packages/sympy/functions/elementary/hyperbolic.py

🟡 **L283** [立即修复]: , implement more if deep stuff here

🟡 **L480** [立即修复]: , implement more if deep stuff here


### venv/lib/python3.13/site-packages/sympy/functions/special/tests/test_bessel.py

🟡 **L514** [立即修复]: could have these return NaN; for now just fix infinite recursion


### venv/lib/python3.13/site-packages/sympy/physics/optics/gaussopt.py

🟡 **L526** [立即修复]: A class Complex may be implemented. The BeamParameter may


### venv/lib/python3.13/site-packages/sympy/physics/quantum/trace.py

🟡 **L189** [立即修复]: : improve this implementation


### venv/lib/python3.13/site-packages/sympy/physics/quantum/spin.py

🟡 **L616** [立即修复]: move evaluation up to represent function/implement elsewhere

🟡 **L1487** [立即修复]: Need hilbert space fix, see issue 5732


### venv/lib/python3.13/site-packages/sympy/physics/units/tests/test_quantities.py

🟡 **L253** [立即修复]: fix this, it should give `m` without `Abs`


### venv/lib/python3.13/site-packages/sympy/physics/quantum/tests/test_printing.py

🟡 **L678** [立即修复]: Fix non-unicode pretty printing


### venv/lib/python3.13/site-packages/sympy/matrices/expressions/hadamard.py

🟡 **L165** [立即修复]: Implement algorithm for rewriting Hadamard product as diagonal matrix


### venv/lib/python3.13/site-packages/sympy/matrices/expressions/tests/test_derivatives.py

🟡 **L435** [立即修复]: not implemented


### venv/lib/python3.13/site-packages/pygments/lexers/parsers.py

🟡 **L396** [立即修复]: finish implementing other possibilities for scope


### venv/lib/python3.13/site-packages/pygments/lexers/css.py

🟡 **L555** [立即修复]: broken, and prone to infinite loops.


### venv/lib/python3.13/site-packages/grpc/beta/_server_adaptations.py

🟡 **L43** [立即修复]: (https://github.com/grpc/grpc/issues/4078): design, implement.


### venv/lib/python3.13/site-packages/grpc/beta/_client_adaptations.py

🟡 **L84** [立即修复]: (https://github.com/grpc/grpc/issues/4078): design, implement.


### venv/lib/python3.13/site-packages/grpc/aio/_channel.py

🟡 **L486** [立即修复]: (xuanwn): Implement this method after we have

🟡 **L491** [立即修复]: (xuanwn): Implement _registered_method after we have

🟡 **L511** [立即修复]: (xuanwn): Implement _registered_method after we have

🟡 **L531** [立即修复]: (xuanwn): Implement _registered_method after we have

🟡 **L551** [立即修复]: (xuanwn): Implement _registered_method after we have


### venv/lib/python3.13/site-packages/grpc/aio/_server.py

🟡 **L68** [立即修复]: (asheshvidyut): fix the value error below

🟡 **L98** [立即修复]: (xuanwn): Implement this for AsyncIO.


### venv/lib/python3.13/site-packages/mpmath/libmp/libhyper.py

🟡 **L914** [立即修复]: recompute at higher precision if the fixed-point mantissa


### venv/lib/python3.13/site-packages/mpmath/functions/zeta.py

🟡 **L238** [立即修复]: fix the interface wrt contexts

🟡 **L385** [立即修复]: this should be implemented low-level

🟡 **L620** [立即修复]: implement for derivatives


### venv/lib/python3.13/site-packages/mpmath/functions/functions.py

🟡 **L174** [立即修复]: tests; improve implementation


### venv/lib/python3.13/site-packages/mpmath/functions/factorials.py

🟡 **L112** [立即修复]: fixme, obviously


### venv/lib/python3.13/site-packages/mpmath/functions/theta.py

🟡 **L926** [立即修复]: write _jacobi_theta2a and _jacobi_theta3a using fixed-point


### venv/lib/python3.13/site-packages/mpmath/matrices/linalg.py

🟡 **L372** [立即修复]: implement this


### venv/lib/python3.13/site-packages/opentelemetry/sdk/_shared_internal/__init__.py

🟡 **L242** [立即修复]: Fix force flush so the timeout is used https://github.com/open-telemetry/opentelemetry-python/issues/4568.


### venv/lib/python3.13/site-packages/IPython/utils/text.py

🟡 **L80** [立即修复]: We need to reimplement type specific displayhook and then add this


### venv/lib/python3.13/site-packages/seaborn/_core/plot.py

🟡 **L606** [立即修复]: PairGrid features not currently implemented: diagonals, corner


### venv/lib/python3.13/site-packages/seaborn/_core/properties.py

🟡 **L623** [立即修复]: implement scales for date variables and any others.


### venv/lib/python3.13/site-packages/seaborn/_core/data.py

🟡 **L200** [立即修复]: this will be rendered unnecessary by the following pandas fix:


### venv/lib/python3.13/site-packages/seaborn/_marks/base.py

🟡 **L294** [立即修复]: should we be implementing fill here too?


### venv/lib/python3.13/site-packages/fsspec/implementations/tar.py

🟡 **L79** [立即修复]: tarfile already implements compression with modes like "'r:gz'",


### venv/lib/python3.13/site-packages/google/protobuf/descriptor.py

🟡 **L27** [立即修复]: Remove this import after fix api_implementation


### venv/lib/python3.13/site-packages/google/protobuf/symbol_database.py

🟡 **L136** [立即修复]: Fix the differences with MessageFactory.


### venv/lib/python3.13/site-packages/google/protobuf/message.py

🟡 **L66** [立即修复]: Remove this once the UPB implementation is improved.


### venv/lib/python3.13/site-packages/google/protobuf/descriptor_database.py

🟡 **L139** [立即修复]: implement this API.

🟡 **L143** [立即修复]: implement this API.


### venv/lib/python3.13/site-packages/google/auth/compute_engine/_metadata.py

🟡 **L144** [立即修复]: implement GCE residency detection on Windows


### venv/lib/python3.13/site-packages/google/protobuf/internal/python_message.py

🟡 **L465** [立即修复]: This may be broken since there may not be

🟡 **L726** [立即修复]: This may be broken since there may not be

🟡 **L1051** [立即修复]: Fix UnknownFieldSet to consider MessageSet extensions,


### venv/lib/python3.13/site-packages/google/protobuf/pyext/cpp_message.py

🟡 **L21** [立即修复]: Remove this import after fix api_implementation


### venv/lib/python3.13/site-packages/jedi/plugins/stdlib.py

🟡 **L196** [立即修复]: implement this if it's a callable.


### venv/lib/python3.13/site-packages/jedi/inference/helpers.py

🟡 **L14** [立即修复]: The implementation below is probably incorrect and not complete.


### venv/lib/python3.13/site-packages/skops/io/_audit.py

🟡 **L294** [立即修复]: FIXME This causes a recursion error when loading a cached


### venv/lib/python3.13/site-packages/skops/io/_utils.py

🟡 **L164** [立即修复]: This should help with fixing recursive references.


### venv/lib/python3.13/site-packages/fontTools/subset/__init__.py

🟡 **L3301** [立即修复]: (behdad) Implement --unicode='*' to choose all cmap'ed


### venv/lib/python3.13/site-packages/fontTools/varLib/__init__.py

🟡 **L190** [立即修复]: (anthrotype) revert this (and 19c4b37) when issue is fixed


### venv/lib/python3.13/site-packages/fontTools/ttLib/removeOverlaps.py

🟡 **L122** [立即修复]: (anthrotype): remove once this Skia bug is fixed


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otConverters.py

🟡 **L873** [立即修复]: Also implement format 4.

🟡 **L1281** [立即修复]: Untangle the implementation of the various lookup-specific formats.


### venv/lib/python3.13/site-packages/sentry_sdk/integrations/openai_agents/spans/ai_client.py

🟡 **L25** [立即修复]: -anton: implement other types of operations. Now "chat" is hardcoded.


### venv/lib/python3.13/site-packages/mlflow/dspy/autolog.py

🟡 **L59** [立即修复]: since this implementation is inconsistent, explore a universal way to solve the issue.


### venv/lib/python3.13/site-packages/mlflow/langchain/model.py

🟡 **L312** [立即修复]: empty output schema if multiple output_keys or is a retriever. fix later!


### venv/lib/python3.13/site-packages/mlflow/llama_index/autolog.py

🟡 **L30** [立即修复]: since this implementation is inconsistent, explore a universal way to solve the issue.


### venv/lib/python3.13/site-packages/mlflow/sklearn/utils.py

🟡 **L999** [立即修复]: Remove when FeatureHasher is implemented in PYPY


### venv/lib/python3.13/site-packages/mlflow/ag2/__init__.py

🟡 **L32** [立即修复]: since this implementation is inconsistent, explore a universal way to solve the issue.


### venv/lib/python3.13/site-packages/mlflow/tracking/fluent.py

🟡 **L3670** [立即修复]: Remove this logic once a feature flag is implemented in Databricks Runtime init logic.


### venv/lib/python3.13/site-packages/mlflow/litellm/__init__.py

🟡 **L33** [立即修复]: since this implementation is inconsistent, explore a universal way to solve the issue.


### venv/lib/python3.13/site-packages/mlflow/openai/autolog.py

🟡 **L68** [立即修复]: since this implementation is inconsistent, explore a universal way to solve the issue.


### venv/lib/python3.13/site-packages/mlflow/deployments/plugin_manager.py

🟡 **L14** [立即修复]: refactor to have a common base class for all the plugin implementation in MLflow


### venv/lib/python3.13/site-packages/mlflow/assistant/providers/claude_code.py

🟡 **L735** [立即修复]: This prefix is not guaranteed to be stable. We should find a better way to


### venv/lib/python3.13/site-packages/mlflow/genai/judges/make_judge.py

🟡 **L267** [立即修复]: Implement logic to allow the LLM to choose the appropriate value type if not specified


### venv/lib/python3.13/site-packages/mlflow/store/tracking/abstract_store.py

🟡 **L391** [立即修复]: ensure NotImplementedError can be translated to 501 error code in mlflow server


### venv/lib/python3.13/site-packages/mlflow/store/tracking/sqlalchemy_store.py

🟡 **L4307** [立即修复]: Implement pagination with page_token

🟡 **L5702** [立即修复]: Implement proper async support


### venv/lib/python3.13/site-packages/mlflow/store/artifact/databricks_models_artifact_repo.py

🟡 **L126** [立即修复]: Change the implementation of this to match how databricks_artifact_repo.py handles this


### venv/lib/python3.13/site-packages/torch/_higher_order_ops/triton_kernel_wrap.py

🟡 **L1390** [立即修复]: remove this when the Triton issue above is fixed


### venv/lib/python3.13/site-packages/torch/_prims/__init__.py

🟡 **L396** [立即修复]: implement dtype validation here, too, or on the corresponding refs

🟡 **L478** [立即修复]: fix number type promotion (bool, complex->float)

🟡 **L2203** [立即修复]: Remove safe casting and implement on reference instead


### venv/lib/python3.13/site-packages/torch/_subclasses/functional_tensor.py

🟡 **L378** [立即修复]: (sparse-team): fixes #133174 but can we do without the relay?


### venv/lib/python3.13/site-packages/torch/_subclasses/fake_tensor.py

🟡 **L2979** [立即修复]: - fix prims complex ops


### venv/lib/python3.13/site-packages/torch/_custom_op/autograd.py

🟡 **L49** [立即修复]: (#101191): Use the actual C++ autograd not implemented fallback,


### venv/lib/python3.13/site-packages/torch/nn/functional.py

🟡 **L5826** [立即修复]: Fix via https://github.com/pytorch/pytorch/issues/75798


### venv/lib/python3.13/site-packages/torch/distributed/device_mesh.py

🟡 **L306** [立即修复]: (yeounoh) implement DeviceMesh backend and register XLA backend.

🟡 **L510** [立即修复]: remove this once we have fixed inside c10d level.


### venv/lib/python3.13/site-packages/torch/fx/graph_module.py

🟡 **L142** [立即修复]: Fix TorchScript BC to avoid breakages like these


### venv/lib/python3.13/site-packages/torch/fx/node.py

🟡 **L587** [立即修复]: THIS IS BROKEN: _get_qualified_name calls `__name__`


### venv/lib/python3.13/site-packages/torch/_prims_common/__init__.py

🟡 **L178** [立即修复]: we should review why this happens and see about fixing it


### venv/lib/python3.13/site-packages/torch/_prims_common/wrappers.py

🟡 **L55** [立即修复]: implement ref.cast with an option to enforce safe casting


### venv/lib/python3.13/site-packages/torch/masked/_ops.py

🟡 **L685** [立即修复]: Implement reductions for dense dimensions for ops with non-zero reduction identities

🟡 **L763** [立即修复]: when dense dimensions are implemented for CSR tensors

🟡 **L846** [立即修复]: implement sparse CSR specific where operator for efficiency


### venv/lib/python3.13/site-packages/torch/_inductor/select_algorithm.py

🟡 **L2756** [立即修复]: (nmacchioni): fix sympy division by zero


### venv/lib/python3.13/site-packages/torch/_inductor/codecache.py

🟡 **L1025** [立即修复]: this check is broken in two ways:


### venv/lib/python3.13/site-packages/torch/_inductor/cpp_builder.py

🟡 **L1563** [立即修复]: fix issue, can't find omp.h


### venv/lib/python3.13/site-packages/torch/_inductor/pattern_matcher.py

🟡 **L2112** [立即修复]: - fix schema


### venv/lib/python3.13/site-packages/torch/_inductor/graph.py

🟡 **L1263** [立即修复]: fix partitioning issue and re-enable for backward

🟡 **L1410** [立即修复]: should really switch to "needs_fixed_stride" constraint on these


### venv/lib/python3.13/site-packages/torch/_inductor/lowering.py

🟡 **L115** [立即修复]: (jansel): we should implement decomps or lowerings for these


### venv/lib/python3.13/site-packages/torch/_inductor/ir.py

🟡 **L3705** [立即修复]: a new class for FixedTransferLayout that output layout is constrained by input layout

🟡 **L7288** [立即修复]: could also be good to have a codegen fix to recognize overlapping elements

🟡 **L8785** [立即修复]: fix


### venv/lib/python3.13/site-packages/torch/_inductor/constant_folding.py

🟡 **L217** [立即修复]: - fix errors with this

🟡 **L224** [立即修复]: - constant folding triton kernel returns the inputs -- fix this


### venv/lib/python3.13/site-packages/torch/_inductor/utils.py

🟡 **L4231** [立即修复]: implement V3_BACKENDS_TUPLE


### venv/lib/python3.13/site-packages/torch/_inductor/decomposition.py

🟡 **L434** [立即修复]: Look into why and fix it (hopefully)


### venv/lib/python3.13/site-packages/torch/_inductor/shape_propagation.py

🟡 **L75** [立即修复]: fix me


### venv/lib/python3.13/site-packages/torch/_inductor/mkldnn_ir.py

🟡 **L119** [立即修复]: <Leslie> cleaned up the fake_tensor trace as Linear implementation


### venv/lib/python3.13/site-packages/torch/_inductor/choices.py

🟡 **L265** [立即修复]: debug and fix


### venv/lib/python3.13/site-packages/torch/_inductor/comm_analysis.py

🟡 **L472** [立即修复]: (ivankobzarev): fix out variants snode_args_kwargs


### venv/lib/python3.13/site-packages/torch/utils/_python_dispatch.py

🟡 **L31** [立即修复]: Limitations and things about enable_torch_dispatch_mode we should fix before exposing it:


### venv/lib/python3.13/site-packages/torch/utils/weak.py

🟡 **L365** [立即修复]: , add _fix_weakref type binding


### venv/lib/python3.13/site-packages/torch/jit/frontend.py

🟡 **L258** [立即修复]: proper overriding analysis when implementing class inheritance


### venv/lib/python3.13/site-packages/torch/jit/annotations.py

🟡 **L454** [立即修复]: Determine if the other cases need to be fixed as well


### venv/lib/python3.13/site-packages/torch/_dynamo/symbolic_convert.py

🟡 **L6184** [立即修复]: fix InstructionTranslator -> InstructionTranslatorBase


### venv/lib/python3.13/site-packages/torch/_dynamo/decorators.py

🟡 **L1611** [立即修复]: also implement nonrecursive patch_dynamo_config/dont_skip_tracing.


### venv/lib/python3.13/site-packages/torch/_refs/__init__.py

🟡 **L210** [立即修复]: add OpInfo (or implement .to)

🟡 **L2985** [立即修复]: fix this to work with meta tensors

🟡 **L6463** [立即修复]: fix inductor rand_like for integer, bool dtypes


### venv/lib/python3.13/site-packages/torch/profiler/_pattern_matcher.py

🟡 **L427** [立即修复]: fixme! Due to lifetime issues of the function name, this field might


### venv/lib/python3.13/site-packages/torch/sparse/_triton_ops.py

🟡 **L1221** [立即修复]: implement checks


### venv/lib/python3.13/site-packages/torch/export/_unlift.py

🟡 **L750** [立即修复]: fix these files to handle guard fns


### venv/lib/python3.13/site-packages/torch/export/_trace.py

🟡 **L1644** [立即修复]: Fix recompile() in  _LazyGraphModule. T207713214


### venv/lib/python3.13/site-packages/torch/distributions/laplace.py

🟡 **L83** [立即修复]: If we ever implement tensor.nextafter, below is what we want ideally.


### venv/lib/python3.13/site-packages/torch/_export/passes/constant_folding.py

🟡 **L135** [立即修复]: - fix errors with this

🟡 **L142** [立即修复]: - constant folding triton kernel returns the inputs -- fix this


### venv/lib/python3.13/site-packages/torch/_export/serde/serialize.py

🟡 **L420** [立即修复]: this should be fixed by deserialization instead.


### venv/lib/python3.13/site-packages/torch/nn/utils/parametrize.py

🟡 **L757** [立即修复]: Fix this for tensor subclasses that are parameters:


### venv/lib/python3.13/site-packages/torch/nn/modules/rnn.py

🟡 **L826** [立即修复]: remove the overriding implementations for LSTM and GRU when TorchScript


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py

🟡 **L5741** [立即修复]: Might need a fix in torch group_norm module

🟡 **L6292** [立即修复]: Once we have proper scoping, stop reimplementing chunk, delete this


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_tensors.py

🟡 **L42** [立即修复]: Implement indexing


### venv/lib/python3.13/site-packages/torch/onnx/_internal/exporter/_building.py

🟡 **L184** [立即修复]: (justinchuby): Implement type promotion logic here.


### venv/lib/python3.13/site-packages/torch/distributed/checkpoint/optimizer.py

🟡 **L200** [立即修复]: The ReadItems will have a displaced MetadataIndex, fix it.


### venv/lib/python3.13/site-packages/torch/distributed/pipelining/_IR.py

🟡 **L1224** [立即修复]: make this implementation out-of-place?


### venv/lib/python3.13/site-packages/torch/distributed/_tools/sac_estimator.py

🟡 **L313** [立即修复]: @sanketpurandare: Fix this by changing the parent of the inplace-op


### venv/lib/python3.13/site-packages/torch/distributed/fsdp/_common_utils.py

🟡 **L394** [立即修复]: Explicitly replacing the checkpoint wrapper prefix is not ideal as


### venv/lib/python3.13/site-packages/torch/distributed/tensor/placement_types.py

🟡 **L314** [立即修复]: (pianpwk): remove the unbacked symbols check and fix AsyncTP pattern matching


### venv/lib/python3.13/site-packages/torch/distributed/elastic/rendezvous/etcd_rendezvous.py

🟡 **L949** [立即修复]: implement timeout


### venv/lib/python3.13/site-packages/torch/distributed/elastic/multiprocessing/api.py

🟡 **L481** [立即修复]: log_line_prefixes can be expanded too


### venv/lib/python3.13/site-packages/torch/distributed/_shard/sharded_optim/api.py

🟡 **L82** [立即修复]: implement state_dict

🟡 **L92** [立即修复]: implement load_state_dict

🟡 **L99** [立即修复]: implement add_param_group


### venv/lib/python3.13/site-packages/torch/distributed/tensor/parallel/fsdp.py

🟡 **L359** [立即修复]: this is a short term fix and we should make the get_unflat_views


### venv/lib/python3.13/site-packages/torch/distributed/tensor/parallel/style.py

🟡 **L531** [立即修复]: re-enable the check once we fix the compile path

🟡 **L682** [立即修复]: re-enable the check once we fix the compile path


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_tensor_ops.py

🟡 **L1486** [立即修复]: fix remaining failures in xfail("unbind") in test_dtensor_ops.py


### venv/lib/python3.13/site-packages/torch/fx/experimental/sym_node.py

🟡 **L1812** [立即修复]: this is an awful implementation


### venv/lib/python3.13/site-packages/torch/fx/experimental/symbolic_shapes.py

🟡 **L7167** [立即修复]: compute hint might have gotten broken here

🟡 **L7446** [立即修复]: Help text about how to use our runtime tests to fix this


### venv/lib/python3.13/site-packages/torch/fx/experimental/proxy_tensor.py

🟡 **L2894** [立即修复]: Would be nice to fix this at the source...


### venv/lib/python3.13/site-packages/torch/_inductor/runtime/triton_heuristics.py

🟡 **L2721** [立即修复]: (jansel): need to fixup src.fn which is now None


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/wrapper.py

🟡 **L3497** [立即修复]: Fix me, MPS does not expose streams now


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/triton.py

🟡 **L3759** [立即修复]: Once the shape propagation PR lands, reimplement this logic:


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp.py

🟡 **L5001** [立即修复]: (jansel): allow fusion pointwise (vars1, ()) suffix?

🟡 **L5028** [立即修复]: we can fix if it allows us to CSE at least one of the variables


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cpp_wrapper_cpu.py

🟡 **L2841** [立即修复]: Only support None and tensor(s) returns for now, SymInt is not implemented yet


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/common.py

🟡 **L2688** [立即修复]: fix me


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/pallas.py

🟡 **L984** [立即修复]: Implement explicit bounds checking with assertions if needed


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/halide.py

🟡 **L1334** [立即修复]: (jansel): implement welford_reduce without fallback


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/triton.py

🟡 **L1043** [立即修复]: make a BaseDeviceConfigHeuristics to handle different device configuration in its own implementation.


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/conv.py

🟡 **L676** [立即修复]: (jansel): try unroll for bigger kernels once fixed:

🟡 **L699** [立即修复]: (jansel): try unroll for bigger kernels once fixed:


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/mm_plus_mm.py

🟡 **L148** [立即修复]: (jansel): support different K values when this is fixed:


### venv/lib/python3.13/site-packages/torch/_inductor/codegen/cutedsl/cutedsl_kernel.py

🟡 **L40** [立即修复]: setting the 'main' kernel w/ this suffix. We have 3 should probably just auto generate this


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/flex/flex_decoding.py

🟡 **L248** [立即修复]: fix autotuning.


### venv/lib/python3.13/site-packages/torch/_inductor/kernel/flex/flex_attention.py

🟡 **L829** [立即修复]: Implement dLSE support in flash-attention backward by folding


### venv/lib/python3.13/site-packages/torch/utils/_sympy/functions.py

🟡 **L379** [立即修复]: if https://github.com/triton-lang/triton/issues/619 is fixed


### venv/lib/python3.13/site-packages/torch/utils/_sympy/reference.py

🟡 **L524** [立即修复]: This is wrong, CPython has a custom implementation of true


### venv/lib/python3.13/site-packages/torch/utils/_sympy/printers.py

🟡 **L477** [立即修复]: PowByNatural: we need to implement our own int-int pow.  Do NOT


### venv/lib/python3.13/site-packages/torch/utils/data/_utils/worker.py

🟡 **L191** [立即修复]: Implement `SeedSequence` like object for `torch.random`


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_typing.py

🟡 **L303** [立即修复]: Fix isinstance bug

🟡 **L360** [立即修复]: Fix isinstance bug

🟡 **L371** [立即修复]: Fix isinstance bug


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/dataframe/dataframes.py

🟡 **L206** [立即修复]: (VitalyFedyunin): Do not use private function here, copy own implementation instead.

🟡 **L456** [立即修复]: (VitalyFedyunin): Must implement all special functions of datapipes


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_nn.py

🟡 **L2649** [立即修复]: remove after implementing reflection pad 3d

🟡 **L3218** [立即修复]: : Fix these discrepancies


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_methods_invocations.py

🟡 **L1376** [立即修复]: exclude_zeros can be removed after https://github.com/pytorch/pytorch/issues/73638 is fixed

🟡 **L1383** [立即修复]: exclude_zeros can be removed after https://github.com/pytorch/pytorch/issues/73638 is fixed

🟡 **L2729** [立即修复]: FIXME

🟡 **L8864** [立即修复]: Derivative wrt. weight not implemented

🟡 **L12664** [立即修复]: Fix test_out_arg_all_dtypes as torch.empty_like(expected_output) where expected_output=op(input)

🟡 **L15731** [立即修复]: FIXME: RuntimeError: "bitwise_or_cuda" not implemented for 'Half'

🟡 **L15750** [立即修复]: FIXME: RuntimeError: "bitwise_xor_cuda" not implemented for 'Half'

🟡 **L17603** [立即修复]: both derivatives are implemented incorrectly

🟡 **L18627** [立即修复]: FIXME

🟡 **L18635** [立即修复]: FIXME, ideally by implemented grad for both inputs

🟡 **L18675** [立即修复]: FIXME, ideally by implementing grad for both inputs

🟡 **L19516** [立即修复]: FIXME tolerance is too high

🟡 **L22083** [立即修复]: FIXME: complex inputs requiring grad error in forward

🟡 **L22090** [立即修复]: implement csr.to_sparse(sample_dim) where sampled_dim is 1.

🟡 **L22556** [立即修复]: Benchmark again with the new implementation


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_mps.py

🟡 **L726** [立即修复]: remove these once downstream function 'aten::_linalg_svd.U' have been implemented

🟡 **L956** [立即修复]: remove these once downstream function 'aten::_linalg_svd.U' have been implemented


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_utils.py

🟡 **L3111** [立即修复]: Revisit the relaxed pairs and check how much work it is to fix the tests that would fail without the relaxation.


### venv/lib/python3.13/site-packages/torch/testing/_internal/jit_utils.py

🟡 **L825** [立即修复]: inplace tests currently fail, fix and add inplace variant


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/_masked.py

🟡 **L562** [立即修复]: "cuda_scatter_gather_base_kernel_func" not implemented for ... (used for sparse_coo inputs)

🟡 **L719** [立即修复]: "cuda_scatter_gather_base_kernel_func" not implemented for ... (used for sparse_coo inputs)

🟡 **L720** [立即修复]: "_segment_reduce_lengths_cpu/cuda" not implemented for ... (used for sparse_csr inputs)

🟡 **L773** [立即修复]: "cuda_scatter_gather_base_kernel_func" not implemented for ... (used for sparse_coo inputs)

🟡 **L774** [立即修复]: "_segment_reduce_lengths_cpu/cuda" not implemented for ... (used for sparse_csr inputs)

🟡 **L900** [立即修复]: "_segment_reduce_lengths_cpu/cuda" not implemented for ... (used for sparse_csr inputs)


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/linalg.py

🟡 **L261** [立即修复]: Fix lu_factor for MPS, because it does not work for all of


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/sparse.py

🟡 **L151** [立即修复]: remove this if-block after gh-98495 is fixed.

🟡 **L217** [立即修复]: remove this if-block after gh-98495 is fixed.

🟡 **L249** [立即修复]: remove this if-block after gh-98495 is fixed.


### venv/lib/python3.13/site-packages/torch/testing/_internal/opinfo/definitions/special.py

🟡 **L69** [立即修复]: eliminate low after gh-106692 is fixed:

🟡 **L260** [立即修复]: FIXME


### venv/lib/python3.13/site-packages/torch/_dynamo/polyfills/builtins.py

🟡 **L66** [立即修复]: (guilhermeleobas): Implement this iterator as a VariableTracker to see if


### venv/lib/python3.13/site-packages/torch/_dynamo/polyfills/itertools.py

🟡 **L211** [立即修复]: use indices = itertools.count() and merge implementation with the else branch


### venv/lib/python3.13/site-packages/torch/ao/quantization/utils.py

🟡 **L131** [立即修复]: reuse is_fixed_qparam_node after we move this function to _lower_to_native_backend.py


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/pattern_utils.py

🟡 **L96** [立即修复]: (future PR): if needed, implement matching for a node


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/n_shadows_utils.py

🟡 **L644** [立即修复]: (future PR): implement this

🟡 **L1106** [立即修复]: (before land): fix string match


### venv/lib/python3.13/site-packages/torch/ao/ns/fx/mappings.py

🟡 **L533** [立即修复]: (future PR): implement shadowing for binary ops and


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/_qnnpack_pt2e.py

🟡 **L26** [立即修复]: need to fix the way we insert observers for this pattern


### venv/lib/python3.13/site-packages/torch/ao/quantization/backend_config/backend_config.py

🟡 **L292** [立即修复]: refer to NativeBackendConfig once that is implemented


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/pattern_utils.py

🟡 **L17** [立即修复]: (future PR): fix the typing on QuantizeHandler (currently a circular dependency)


### venv/lib/python3.13/site-packages/torch/ao/pruning/sparsifier/utils.py

🟡 **L42** [立即修复]: Fix this typing, as Type[Module] has no attribute "from_dense"


### venv/lib/python3.13/site-packages/limits/aio/storage/mongodb.py

🟡 **L79** [立即修复]: Fix this hack. It was noticed when running a benchmark


### venv/lib/python3.13/site-packages/mpl_toolkits/mplot3d/axes3d.py

🟡 **L3161** [立即修复]: Implement auto-scaling function for Patch3DCollection


### venv/lib/python3.13/site-packages/sqlalchemy/orm/context.py

🟡 **L2942** [立即修复]: we might be able to implement this but for now


### venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py

🟡 **L272** [立即修复]: this is not to be part of 2.0.  implement rudimentary binary


### venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py

🟡 **L2148** [立即修复]: this will be fixed by #13018


### venv/lib/python3.13/site-packages/sqlalchemy/sql/sqltypes.py

🟡 **L896** [立即修复]: this is useless for real world scenarios; implement


### venv/lib/python3.13/site-packages/numpy/f2py/symbolic.py

🟡 **L570** [立即修复]: implement a method for deciding when __call__ should


### venv/lib/python3.13/site-packages/numpy/ma/tests/test_old_ma.py

🟡 **L654** [立即修复]: FIXME: Find out what the following raises a warning in r8247


### venv/lib/python3.13/site-packages/numpy/f2py/tests/test_docs.py

🟡 **L59** [立即修复]: implement test methods for other example Fortran codes


### venv/lib/python3.13/site-packages/numpy/lib/tests/test_function_base.py

🟡 **L3721** [立即修复]: Note that times have dubious rounding as of fixing NaTs!


### venv/lib/python3.13/site-packages/numpy/lib/tests/test_recfunctions.py

🟡 **L548** [立即修复]: , this test looks incomplete and broken

🟡 **L818** [立即修复]: , this test is broken


### venv/lib/python3.13/site-packages/pip/_vendor/requests/models.py

🟡 **L685** [立即修复]: can be fixed by flipping the conditionals


### venv/lib/python3.13/site-packages/pip/_vendor/urllib3/connection.py

🟡 **L336** [立即修复]: Fix tunnel so it doesn't depend on self.sock state.

🟡 **L567** [立即修复]: should we implement it everywhere?


### venv/lib/python3.13/site-packages/pip/_vendor/pkg_resources/__init__.py

🟡 **L3308** [立即修复]: remove this except clause when python/cpython#103632 is fixed.


### venv/lib/python3.13/site-packages/sklearn/datasets/_svmlight_format_io.py

🟡 **L576** [立即修复]: simplify interfaces and implementations in _svmlight_format_fast.pyx.


### venv/lib/python3.13/site-packages/sklearn/tests/test_common.py

🟡 **L224** [立即修复]: FIX MLP to not check validation set during MLP


### venv/lib/python3.13/site-packages/sklearn/tests/test_multioutput.py

🟡 **L198** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/tests/test_calibration.py

🟡 **L215** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/tests/test_pipeline.py

🟡 **L1041** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/utils/fixes.py

🟡 **L91** [立即修复]: Fuse the modern implementations of _sparse_min_max and _sparse_nan_min_max


### venv/lib/python3.13/site-packages/sklearn/utils/_array_api.py

🟡 **L879** [立即修复]: Remove this once https://github.com/scipy/scipy/issues/21736 is fixed


### venv/lib/python3.13/site-packages/sklearn/neighbors/_classification.py

🟡 **L342** [立即修复]: Implement efficient multi-output solution


### venv/lib/python3.13/site-packages/sklearn/neighbors/_kde.py

🟡 **L40** [立即修复]: implement a brute force version for testing purposes

🟡 **L334** [立即修复]: implement sampling for other valid kernel shapes


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_pairwise_distances_reduction.py

🟡 **L698** [立即修复]: the current Cython implementation is too slow for a large number of


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_pairwise.py

🟡 **L242** [立即修复]: Fix manhattan_distances to preserve dtype.

🟡 **L253** [立即修复]: Fix manhattan_distances to preserve dtype.

🟡 **L1842** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_classification.py

🟡 **L3213** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/metrics/_pairwise_distances_reduction/_dispatcher.py

🟡 **L76** [立即修复]: implement a stable simultaneous_sort.

🟡 **L105** [立即修复]: the current Cython implementation is too slow for a large number of

🟡 **L472** [立即修复]: implement Euclidean specialization using GEMM.

🟡 **L640** [立即修复]: implement Euclidean specialization using GEMM.


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py

🟡 **L1552** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_bagging.py

🟡 **L471** [立即修复]: remove mark once loky bug is fixed:

🟡 **L515** [立即修复]: remove mark once loky bug is fixed:

🟡 **L556** [立即修复]: remove mark once loky bug is fixed:

🟡 **L800** [立即修复]: (slep006): remove block when default routing is implemented


### venv/lib/python3.13/site-packages/sklearn/cluster/tests/test_mean_shift.py

🟡 **L81** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/cluster/tests/test_affinity_propagation.py

🟡 **L278** [立即修复]: ; this test is broken with different random states, needs to be revisited


### venv/lib/python3.13/site-packages/sklearn/cluster/_hdbscan/hdbscan.py

🟡 **L792** [立即修复]: Support np.nan in Cython implementation for precomputed

🟡 **L958** [立即修复]: Implement weighted argmin PWD backend


### venv/lib/python3.13/site-packages/sklearn/compose/tests/test_column_transformer.py

🟡 **L2661** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py

🟡 **L869** [立即修复]: the random state is fixed in the following test because SAG fails

🟡 **L1792** [立即修复]: Random state is fixed in order to make the test pass

🟡 **L1826** [立即修复]: Random state is fixed in order to make the test pass

🟡 **L1869** [立即修复]: Random state is fixed in order to make the test pass


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_common.py

🟡 **L68** [立即修复]: FIx SAGA which fails badly with sample_weights.


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_sag.py

🟡 **L490** [立即修复]: uncomment when sparse Ridge with intercept will be fixed (#4710)


### venv/lib/python3.13/site-packages/sklearn/utils/_test_common/instance_generator.py

🟡 **L1116** [立即修复]: fix sample_weight handling of this estimator, see meta-issue #16298

🟡 **L1138** [立即修复]: fix sample_weight handling of this estimator when probability=False

🟡 **L1152** [立即修复]: fix sample_weight handling of this estimator, see meta-issue #16298

🟡 **L1170** [立即修复]: fix sample_weight handling of this estimator, see meta-issue #16298

🟡 **L1327** [立即修复]: fix sample_weight handling of this estimator when probability=False

🟡 **L1338** [立即修复]: fix sample_weight handling of this estimator, see meta-issue #16298


### venv/lib/python3.13/site-packages/sklearn/inspection/tests/test_partial_dependence.py

🟡 **L703** [立即修复]: remove/fix when PDP supports HGBT with sample weights


### venv/lib/python3.13/site-packages/sklearn/manifold/tests/test_mds.py

🟡 **L127** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/model_selection/tests/test_search.py

🟡 **L2105** [立即修复]: remove mark once loky bug is fixed:

🟡 **L2133** [立即修复]: remove mark once loky bug is fixed:

🟡 **L2635** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/decomposition/tests/test_dict_learning.py

🟡 **L40** [立即修复]: remove mark once loky bug is fixed:

🟡 **L223** [立即修复]: remove mark once loky bug is fixed:

🟡 **L244** [立即修复]: remove mark once loky bug is fixed:

🟡 **L638** [立即修复]: remove mark once loky bug is fixed:

🟡 **L993** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/decomposition/tests/test_online_lda.py

🟡 **L187** [立即修复]: remove mark once loky bug is fixed:

🟡 **L212** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/decomposition/tests/test_sparse_pca.py

🟡 **L77** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/neighbors/tests/test_kd_tree.py

🟡 **L31** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/sklearn/neighbors/tests/test_neighbors.py

🟡 **L2102** [立即修复]: remove mark once loky bug is fixed:


### venv/lib/python3.13/site-packages/prompt_toolkit/contrib/regular_languages/regex_parser.py

🟡 **L261** [立即修复]: implement!


### venv/lib/python3.13/site-packages/prompt_toolkit/key_binding/bindings/vi.py

🟡 **L629** [立即修复]: implement 'arg'


### venv/lib/python3.13/site-packages/narwhals/_sql/expr_str.py

🟡 **L148** [立即修复]: (unassigned): implement `window_func` like we do in `Expr.cast`


### venv/lib/python3.13/site-packages/narwhals/_arrow/dataframe.py

🟡 **L319** [立即修复]: @dangotbanned: Fix upstream with `pa.ChunkedArray.to_pylist(self) -> list[Any]:`

🟡 **L321** [立即修复]: @dangotbanned: Fix upstream, it is actually much narrower

🟡 **L336** [立即修复]: @dangotbanned: Fix upstream with `pa.ChunkedArray.to_pylist(self) -> list[Any]:`


### venv/lib/python3.13/site-packages/curl_cffi/cli/run.py

🟡 **L107** [立即修复]: implement body checking


### venv/lib/python3.13/site-packages/tensorboard/util/encoder.py

🟡 **L46** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L87** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/util/op_evaluator.py

🟡 **L69** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/projector/metadata.py

🟡 **L25** [立即修复]: (@decentralion): Fix duplication when we find a permanent home for the


### venv/lib/python3.13/site-packages/tensorboard/plugins/custom_scalar/summary.py

🟡 **L38** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L64** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/pr_curve/summary.py

🟡 **L82** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L207** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L305** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L424** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L492** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L546** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/image/summary.py

🟡 **L68** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L133** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/audio/summary.py

🟡 **L98** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L188** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/debugger_v2/debugger_v2_plugin.py

🟡 **L67** [立即修复]: (cais): Implement factory for DataProvider that takes into account

🟡 **L74** [立即修复]: (cais): Add routes as they are implemented.


### venv/lib/python3.13/site-packages/tensorboard/plugins/debugger_v2/debug_data_provider.py

🟡 **L199** [立即修复]: (cais): Implement support for trace_id once joining of eager

🟡 **L252** [立即修复]: (cais): Implement support for trace_id once joining of eager

🟡 **L540** [立即修复]: (cais): Implement this.


### venv/lib/python3.13/site-packages/tensorboard/plugins/debugger_v2/debug_data_multiplexer.py

🟡 **L405** [立即修复]: (cais): Implement support for trace_id once the joining of eager

🟡 **L438** [立即修复]: (cais): Implement support for trace_id once the joining of eager


### venv/lib/python3.13/site-packages/tensorboard/plugins/text/summary.py

🟡 **L57** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L94** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/scalar/summary.py

🟡 **L51** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L85** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/plugins/histogram/summary.py

🟡 **L54** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L146** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.

🟡 **L185** [立即修复]: (nickfelt): remove on-demand imports once dep situation is fixed.


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_file_loader.py

🟡 **L56** [立即修复]: (#1711): Reshape stub implementation to fit tf_record_iterator API


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/data_provider.py

🟡 **L387** [立即修复]: (davidsoergel): deduplicate with other implementations


### venv/lib/python3.13/site-packages/sb3_contrib/crossq/crossq.py

🟡 **L71** [立即修复]: Implement CnnPolicy and MultiInputPolicy


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_cairo.py

🟡 **L301** [立即修复]: The following doesn't properly implement a stack-like behavior


### venv/lib/python3.13/site-packages/matplotlib/backends/backend_pdf.py

🟡 **L2158** [立即修复]: fix positioning and encoding


### venv/lib/python3.13/site-packages/uvicorn/protocols/websockets/wsproto_impl.py

🟡 **L167** [立即修复]: Remove `type: ignore` when wsproto fixes the type annotation.


### venv/lib/python3.13/site-packages/numba/experimental/function_type.py

🟡 **L105** [立即修复]: implement support for pytypes.FunctionType, ctypes.CFUNCTYPE


### venv/lib/python3.13/site-packages/numba/core/ir_utils.py

🟡 **L459** [立即修复]: raise NotImplementedError("no replacement for IR node: ", stmt)


### venv/lib/python3.13/site-packages/numba/core/extending.py

🟡 **L187** [立即修复]: implement setters


### venv/lib/python3.13/site-packages/numba/tests/test_generators.py

🟡 **L467** [立即修复]: fix nested generator and MemoryLeakMixin


### venv/lib/python3.13/site-packages/numba/tests/test_mixed_tuple_unroller.py

🟡 **L1144** [立即修复]: fix


### venv/lib/python3.13/site-packages/numba/tests/test_stencils.py

🟡 **L1636** [立即修复]: add check should this be implemented

🟡 **L1994** [立即修复]: add check should this be implemented

🟡 **L3165** [立即修复]: add check should this be implemented

🟡 **L3193** [立即修复]: add check should this be implemented


### venv/lib/python3.13/site-packages/numba/tests/test_ufuncs.py

🟡 **L1676** [立即修复]: fix issue #758


### venv/lib/python3.13/site-packages/numba/cpython/charseq.py

🟡 **L656** [立即修复]: implement isupper for Bytes

🟡 **L671** [立即修复]: implement upper for Bytes


### venv/lib/python3.13/site-packages/numba/parfors/parfor_lowering.py

🟡 **L707** [立即修复]: use prefix + class number instead of single char


### venv/lib/python3.13/site-packages/numba/parfors/parfor.py

🟡 **L236** [立即修复]: evaluate dotvm implementation options

🟡 **L2702** [立即修复]: Fix this issue... the code didn't manage to trace the


### venv/lib/python3.13/site-packages/numba/core/typing/bufproto.py

🟡 **L22** [立即修复]: FIXME We need to modify the following Map to use Python Types.


### venv/lib/python3.13/site-packages/numba/core/annotations/type_annotations.py

🟡 **L99** [立即修复]: fix parfor lowering so that typemap is valid.


### venv/lib/python3.13/site-packages/torchgen/operator_versions/gen_mobile_upgraders.py

🟡 **L270** [立即修复]: remove the skip after these two operators schemas are fixed

🟡 **L328** [立即修复]: remove the skip after these two operators schemas are fixed


### venv/lib/python3.13/site-packages/torchgen/api/cpp.py

🟡 **L166** [立即修复]: fix this discrepancy


### venv/lib/python3.13/site-packages/setuptools/tests/test_build_py.py

🟡 **L169** [立即修复]: To fix #3260 we need some transition period to deprecate the

🟡 **L199** [立即修复]: Enforce the following assertion once #3260 is fixed


### venv/lib/python3.13/site-packages/setuptools/tests/fixtures.py

🟡 **L137** [立即修复]: Use `--no-wheel` when setuptools implements its own bdist_wheel


### venv/lib/python3.13/site-packages/greenlet/tests/test_greenlet.py

🟡 **L231** [立即修复]: FIXME Make that work.


### venv/lib/python3.13/site-packages/eventlet/green/thread.py

🟡 **L25** [立即修复]: this is a dummy code, reimplementing this may be needed:


### venv/lib/python3.13/site-packages/pydantic/_internal/_docs_extraction.py

🟡 **L103** [立即修复]: remove this implementation when we drop support for Python 3.12:


### venv/lib/python3.13/site-packages/pydantic/_internal/_typing_extra.py

🟡 **L144** [立即修复]: implement `is_finalvar_annotation` as Final can be wrapped with other special forms:


### venv/lib/python3.13/site-packages/polars/series/series.py

🟡 **L1557** [立即修复]: implement for these types without casting to series


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/kde.py

🟡 **L577** [立即修复]: Fix this?


### venv/lib/python3.13/site-packages/statsmodels/discrete/discrete_model.py

🟡 **L3751** [立即修复]: Fix NBin _check_perfect_pred

🟡 **L4214** [立即修复]: Fix doc string


### venv/lib/python3.13/site-packages/statsmodels/discrete/truncated_model.py

🟡 **L1429** [立即修复]: this is to fix df_resid, should be automatic but is not


### venv/lib/python3.13/site-packages/statsmodels/iolib/summary.py

🟡 **L233** [立即修复]: JP the rest needs to be fixed, similar to summary in linear_model


### venv/lib/python3.13/site-packages/statsmodels/sandbox/bspline.py

🟡 **L209** [立即修复]: `order` should be actual spline order (implemented as order+1)


### venv/lib/python3.13/site-packages/statsmodels/sandbox/gam.py

🟡 **L42** [立即修复]: fix iteration, do not define class with iterator methods, use looping;


### venv/lib/python3.13/site-packages/statsmodels/regression/linear_model.py

🟡 **L2** [立即修复]: Fix issue with constant and GLS

🟡 **L1707** [立即修复]: fix writable example


### venv/lib/python3.13/site-packages/statsmodels/base/model.py

🟡 **L2154** [立即修复]: not yet implemented, maybe skip - use partial


### venv/lib/python3.13/site-packages/statsmodels/stats/contrast.py

🟡 **L287** [立即修复]: fix docstring after usage is settled


### venv/lib/python3.13/site-packages/statsmodels/nonparametric/tests/test_kde.py

🟡 **L320** [立即修复]: in docstring but not implemented in kernels


### venv/lib/python3.13/site-packages/statsmodels/sandbox/nonparametric/smoothers.py

🟡 **L99** [立即修复]: undo adjustments and fix dimensions correctly


### venv/lib/python3.13/site-packages/statsmodels/sandbox/stats/multicomp.py

🟡 **L893** [立即修复]: : print(statments, fix


### venv/lib/python3.13/site-packages/statsmodels/sandbox/regression/tests/test_gmm.py

🟡 **L702** [立即修复]: llf raise NotImplementedError


### venv/lib/python3.13/site-packages/statsmodels/tsa/statespace/mlemodel.py

🟡 **L2309** [立即修复]: seems like maybe self.fixed_params should be the dictionary

🟡 **L4065** [立即修复]: `append` should fix this k_endog=1 issue for us


### venv/lib/python3.13/site-packages/statsmodels/tsa/interp/denton.py

🟡 **L82** [立即修复]: take code in the string at the end and implement Denton's original


### venv/lib/python3.13/site-packages/statsmodels/tsa/holtwinters/model.py

🟡 **L1213** [立即修复]: Fix for short m


### venv/lib/python3.13/site-packages/statsmodels/tsa/exponential_smoothing/base.py

🟡 **L336** [立即修复]: seems like maybe self.fixed_params should be the dictionary


### venv/lib/python3.13/site-packages/statsmodels/tsa/base/tsa_model.py

🟡 **L857** [立即修复]: This is an antipattern, fix/remove with VAR


### venv/lib/python3.13/site-packages/statsmodels/regression/tests/test_robustcov.py

🟡 **L24** [立即修复]: implement test_hac_simple

🟡 **L40** [立即修复]: if the t_test call is expensive, possibly make it a fixture?


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_statstools.py

🟡 **L75** [立即修复]: fix precision in these test with relative tolerance


### venv/lib/python3.13/site-packages/statsmodels/stats/tests/test_diagnostic_other.py

🟡 **L24** [立即修复]: fix API, returns of functions


### venv/lib/python3.13/site-packages/scipy/linalg/_decomp.py

🟡 **L827** [立即修复]: implement this somewhen, for now go with builtin values

🟡 **L833** [立即修复]: implement this somewhen, for now go with builtin values


### venv/lib/python3.13/site-packages/scipy/optimize/_linprog_ip.py

🟡 **L92** [立即修复]: revert this suppress_warning once the warning bug fix in


### venv/lib/python3.13/site-packages/scipy/optimize/_direct_py.py

🟡 **L256** [立即修复]: fix disp argument


### venv/lib/python3.13/site-packages/scipy/sparse/_data.py

🟡 **L18** [立即修复]: implement all relevant operations


### venv/lib/python3.13/site-packages/scipy/sparse/_dok.py

🟡 **L601** [立即修复]: implement resize across dimensions


### venv/lib/python3.13/site-packages/scipy/signal/_delegators.py

🟡 **L320** [立即修复]: fix me - `prominence` is not necessarily an array.


### venv/lib/python3.13/site-packages/scipy/optimize/_trustregion_constr/projections.py

🟡 **L61** [立即修复]: revert this once the warning bug fix in sksparse is merged/released


### venv/lib/python3.13/site-packages/scipy/spatial/transform/_rotation_xp.py

🟡 **L105** [立即修复]: Revisit this implementation if the array API supports mixed integer and


### venv/lib/python3.13/site-packages/scipy/spatial/transform/_rotation.py

🟡 **L2146** [立即修复]: We defer the implementation of groups for arbitrary Array API frameworks


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_morestats.py

🟡 **L2943** [立即修复]: add method "pearsonr" after fix overflow issue

🟡 **L2963** [立即修复]: add method "pearsonr" after fix overflow issue


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_mstats_extras.py

🟡 **L43** [立即修复]: check that implementation is correct.


### venv/lib/python3.13/site-packages/scipy/stats/tests/test_distributions.py

🟡 **L9181** [立即修复]: this is only a quick-and-dirty test of a quick-and-dirty bugfix.


### venv/lib/python3.13/site-packages/pandas/core/algorithms.py

🟡 **L1421** [立即修复]: can diff_2d dtype specialization troubles be fixed by defining


### venv/lib/python3.13/site-packages/pandas/io/stata.py

🟡 **L1865** [立即修复]: can we fix that?


### venv/lib/python3.13/site-packages/pandas/tests/test_downstream.py

🟡 **L322** [立即修复]: (GH#44431) these raise on memoryview and attempted fix


### venv/lib/python3.13/site-packages/pandas/core/interchange/column.py

🟡 **L115** [立即修复]: chunks are implemented now, probably this should return something

🟡 **L348** [立即修复]: this for-loop is slow; can be implemented in Cython/C/C++ later

🟡 **L418** [立即修复]: implement for other bit/byte masks?


### venv/lib/python3.13/site-packages/pandas/core/dtypes/common.py

🟡 **L1519** [立即修复]: Implement this properly


### venv/lib/python3.13/site-packages/pandas/core/groupby/grouper.py

🟡 **L402** [立即修复]: why does putting na_position="first" fix datetimelike cases?


### venv/lib/python3.13/site-packages/pandas/core/arrays/interval.py

🟡 **L1245** [立即修复]: implement this is a non-naive way!


### venv/lib/python3.13/site-packages/pandas/core/arrays/datetimes.py

🟡 **L1103** [立即修复]: Also for fixed-offsets


### venv/lib/python3.13/site-packages/pandas/core/arrays/numeric.py

🟡 **L93** [立即修复]: this "if" can be removed when requiring pyarrow >= 10.0, which fixed


### venv/lib/python3.13/site-packages/pandas/core/arrays/datetimelike.py

🟡 **L708** [立即修复]: Could use from_sequence_of_strings if implemented


### venv/lib/python3.13/site-packages/pandas/core/indexes/base.py

🟡 **L5825** [立即修复]: will be fixed when ExtensionArray.searchsorted() is fixed


### venv/lib/python3.13/site-packages/pandas/core/arrays/arrow/array.py

🟡 **L1143** [立即修复]: remove try/except wrapper if/when pyarrow implements

🟡 **L1193** [立即修复]: remove try/except wrapper if/when pyarrow implements

🟡 **L1392** [立即修复]: ArrowNotImplementedError: Function fill_null has no


### venv/lib/python3.13/site-packages/pandas/tests/apply/test_frame_apply.py

🟡 **L1709** [立即修复]: the result below is wrong, should be fixed (GH53325)


### venv/lib/python3.13/site-packages/pandas/tests/extension/test_arrow.py

🟡 **L1444** [立即修复]: Redundant with test_getitem_scalar once arrow_dtype exists in data fixture


### venv/lib/python3.13/site-packages/pandas/tests/resample/test_resample_api.py

🟡 **L380** [立即修复]: (GH#14008): once GH 14008 is fixed, move these tests into


### venv/lib/python3.13/site-packages/pandas/tests/io/test_sql.py

🟡 **L1860** [立即修复]: clean up types_data_frame fixture

🟡 **L3419** [立即修复]: (GH#36465): remove this version check after GH 36465 is fixed


### venv/lib/python3.13/site-packages/pandas/tests/groupby/test_categorical.py

🟡 **L1432** [立即修复]: implemented SeriesGroupBy.corrwith. See GH 32293


### venv/lib/python3.13/site-packages/pandas/tests/indexes/test_base.py

🟡 **L505** [立即修复]: Replace with fixturesult

🟡 **L775** [立即修复]: Parametrize numeric and str tests after self.strIndex fixture


### venv/lib/python3.13/site-packages/pandas/tests/groupby/transform/test_transform.py

🟡 **L1305** [立即修复]: implement SeriesGroupBy.corrwith


### venv/lib/python3.13/site-packages/pandas/tests/arrays/interval/test_overlaps.py

🟡 **L62** [立即修复]: modify this test when implemented


### venv/lib/python3.13/site-packages/pandas/tests/arrays/integer/test_function.py

🟡 **L199** [立即修复]: (jreback) - these need testing / are broken


### venv/lib/python3.13/site-packages/pandas/tests/scalar/timedelta/test_constructors.py

🟡 **L466** [立即修复]: parametrize over units just above/below the implementation bounds


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/test_partial_slicing.py

🟡 **L44** [立即修复]: fix these accessors!


### venv/lib/python3.13/site-packages/_pytest/mark/structures.py

🟡 **L158** [立即修复]: Refactor to fix this type-ignore. Currently the following


### venv/lib/python3.13/site-packages/pyarrow/tests/conftest.py

🟡 **L146** [立即修复]: (kszucs): move the following fixtures to test_fs.py once the previous


### venv/lib/python3.13/site-packages/pyarrow/tests/test_gandiva.py

🟡 **L158** [立即修复]: Implement reasonable support for timestamp, time & date.


### venv/lib/python3.13/site-packages/pyarrow/tests/test_pandas.py

🟡 **L1733** [立即修复]: remove if https://github.com/apache/arrow/issues/15047 is fixed


### application/services/stock_code_validator.py

🟡 **L174** [立即修复]: 可以基于编辑距离、拼音等算法实现更智能的匹配


### application/services/combo_strategy_backtest_service.py

🟡 **L422** [立即修复]: Implement in Task 3


### application/services/game_alert_service.py

🟡 **L233** [立即修复]: 实现持仓风险检查

🟡 **L298** [立即修复]: 实现订阅逻辑（存储到数据库）


### application/services/data_validator.py

🟡 **L243** [立即修复]: 实现特殊情况判断逻辑


### application/services/pool_scan_scheduler.py

🟡 **L85** [立即修复]: 实现通知逻辑（邮件、飞书、钉钉等）


### application/services/smart_scheduler.py

🟡 **L87** [立即修复]: 实现重试逻辑


### application/services/realtime_signal_service.py

🟡 **L219** [立即修复]: 实现分钟级K线获取 + 滚动指标计算


### application/services/strategy_performance_stats.py

🟡 **L437** [立即修复]: 实现数据库查询逻辑


### application/services/strategy_execution_service.py

🟡 **L463** [立即修复]: Implement actual order creation via OrderRepository


### infrastructure/scheduler/scheduled_tasks.py

🟡 **L23** [立即修复]: implement actual CSI 300 component retrieval


### infrastructure/scheduler/signal_execution_job.py

🟡 **L69** [立即修复]: 实现策略执行逻辑


### infrastructure/jobs/risk_check_job.py

🟡 **L113** [立即修复]: 实现更准确的历史账户价值查询


### infrastructure/jobs/weekly_report_job.py

🟡 **L79** [立即修复]: 实现准确的历史账户价值查询


### domain/backtest/engine/__init__.py

🟡 **L98** [立即修复]: File not yet implemented


### venv/lib/python3.13/site-packages/backtrader/feed.py

🟢 **L190** [已废弃]: These two are never used and could be removed

🟢 **L769** [已废弃]: if removed from guest, remove here too


### venv/lib/python3.13/site-packages/torchgen/gen.py

🟢 **L2815** [已废弃]: --op-registration-whitelist will be removed when all call-sites


### venv/lib/python3.13/site-packages/pydantic/mypy.py

🟢 **L820** [已废弃]: this path should be removed (see https://github.com/pydantic/pydantic/issues/11119)


### venv/lib/python3.13/site-packages/pydantic/main.py

🟢 **L4** [已废弃]: v3 fallback to `dict` when the deprecated `dict` method gets removed.


### venv/lib/python3.13/site-packages/gymnasium/wrappers/jax_to_torch.py

🟢 **L90** [已废弃]: Device was part of the public API, but should be removed in favor of _env_device and


### venv/lib/python3.13/site-packages/cvxpy/expressions/expression.py

🟢 **L740** [已废弃]: remove special case once CPP backend is removed

🟢 **L743** [已废弃]: cleanup once CPP backend is removed


### venv/lib/python3.13/site-packages/sympy/tensor/array/expressions/from_array_to_matrix.py

🟢 **L448** [已废弃]: check if subremoved should be permuted as well...


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_stochastic_process.py

🟢 **L77** [已废弃]: Restore tests once warnings are removed

🟢 **L109** [已废弃]: Restore tests once warnings are removed

🟢 **L408** [已废弃]: Restore tests once warnings are removed


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_continuous_rv.py

🟢 **L677** [已废弃]: Restore tests once warnings are removed

🟢 **L1348** [已废弃]: Restore tests once warnings are removed

🟢 **L1358** [已废弃]: Restore tests once warnings are removed


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_mix.py

🟢 **L80** [已废弃]: Restore tests once warnings are removed


### venv/lib/python3.13/site-packages/sympy/stats/tests/test_compound_rv.py

🟢 **L90** [已废弃]: Restore tests once warnings are removed


### venv/lib/python3.13/site-packages/llvmlite/binding/typeref.py

🟢 **L7** [已废弃]: Remove `opaque_pointers_enabled' when TP's are removed.

🟢 **L115** [已废弃]: Remove me once typed pointers support is removed.

🟢 **L229** [已废弃]: Remove me once typed pointers support is removed.


### venv/lib/python3.13/site-packages/fontTools/ttLib/tables/otBase.py

🟢 **L1011** [已废弃]: Following hack to be removed by rewriting how FormatSwitching tables


### venv/lib/python3.13/site-packages/mlflow/gateway/app.py

🟢 **L330** [已废弃]: Remove the deprecated endpoint

🟢 **L382** [已废弃]: Remove the deprecated endpoint


### venv/lib/python3.13/site-packages/torch/distributed/distributed_c10d.py

🟢 **L2212** [已废弃]: once UCC plugin is fully deprecated, remove


### venv/lib/python3.13/site-packages/torch/fx/proxy.py

🟢 **L165** [已废弃]: deprecated

🟢 **L166** [已废弃]: deprecated

🟢 **L237** [已废弃]: node_name_to_scope will be deprecated in favor of


### venv/lib/python3.13/site-packages/torch/_inductor/codecache.py

🟢 **L684** [已废弃]: pickler.fast is technically deprecated. Will this work on new python versions?


### venv/lib/python3.13/site-packages/torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py

🟢 **L1373** [已废弃]: (justinchuby): Looks like this op is deprecated in torch


### venv/lib/python3.13/site-packages/torch/distributed/_local_tensor/__init__.py

🟢 **L1537** [已废弃]: This should either be removed or documented why it's necessary.

🟢 **L1551** [已废弃]: This should either be removed or documented why it's necessary.


### venv/lib/python3.13/site-packages/torch/distributed/tensor/_ops/_pointwise_ops.py

🟢 **L395** [已废弃]: positive should be removed once CIA (Copy Is All) optimizes it away.


### venv/lib/python3.13/site-packages/torch/fx/experimental/optimization.py

🟢 **L178** [已废弃]: Determine whether this can be removed after type inference.


### venv/lib/python3.13/site-packages/torch/_inductor/template_heuristics/triton.py

🟢 **L2891** [已废弃]: (coconutruben): deprecate once autoheuristic is deprecated

🟢 **L3198** [已废弃]: (coconutruben): deprecate once autoheuristic is deprecated


### venv/lib/python3.13/site-packages/torch/utils/data/datapipes/_typing.py

🟢 **L16** [已废弃]: Use TypeAlias when Python 3.6 is deprecated


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_nn.py

🟢 **L2821** [已废弃]: This code can path can be removed if #61309 is resolved


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/object_protocol.py

🟢 **L1641** [已废弃]: can trace this once TypingVariable is removed


### venv/lib/python3.13/site-packages/torch/_dynamo/variables/torch.py

🟢 **L3823** [已废弃]: [@lucaskabela]: Remove the behavior below since it is deprecated


### venv/lib/python3.13/site-packages/torch/ao/quantization/qconfig.py

🟢 **L52** [已废弃]: deprecated, remove


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/quantize_handler.py

🟢 **L219** [已废弃]: not used, can be removed after torch.ao.quantization namespace is deprecated

🟢 **L224** [已废弃]: not used, can be removed after torch.ao.quantization namespace is deprecated


### venv/lib/python3.13/site-packages/sqlalchemy/orm/query.py

🟢 **L560** [已废弃]: this event needs to be deprecated, as it currently applies


### venv/lib/python3.13/site-packages/numpy/fft/__init__.py

🟢 **L204** [已废弃]: `numpy.fft.helper`` was deprecated in NumPy 2.0. It should


### venv/lib/python3.13/site-packages/pip/_internal/build_env/base.py

🟢 **L26** [已废弃]: simplify this data model when the legacy subprocess installer is removed


### venv/lib/python3.13/site-packages/sklearn/metrics/_scorer.py

🟢 **L317** [已废弃]: (1.11): remove this when sample_weight is removed from the `__call__`


### venv/lib/python3.13/site-packages/sklearn/metrics/pairwise.py

🟢 **L2022** [已废弃]: below 2 lines can be removed once min scipy >= 1.14. Support for


### venv/lib/python3.13/site-packages/sklearn/tests/test_common.py

🟢 **L270** [已废弃]: As more modules support get_feature_names_out they should be removed


### venv/lib/python3.13/site-packages/sklearn/tests/test_base.py

🟢 **L246** [已废弃]: (1.11): remove svc test for predict_proba after it is deprecated


### venv/lib/python3.13/site-packages/sklearn/linear_model/_logistic.py

🟢 **L1994** [已废弃]: (1.11): remove this when sample_weight as positional arg is removed

🟢 **L2515** [已废弃]: (1.11): remove this when sample_weight is removed from the `score`


### venv/lib/python3.13/site-packages/sklearn/utils/_plotting.py

🟢 **L185** [已废弃]: Remove once kwargs deprecated on all displays


### venv/lib/python3.13/site-packages/sklearn/preprocessing/_target_encoder.py

🟢 **L238** [已废弃]: (1.11) remove `shuffle` and `random_state` params, which had been deprecated


### venv/lib/python3.13/site-packages/sklearn/model_selection/_validation.py

🟢 **L62** [已废弃]: (SLEP6): To be removed when set_config(enable_metadata_routing=False) is not


### venv/lib/python3.13/site-packages/sklearn/tree/tests/test_tree.py

🟢 **L269** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L333** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L348** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L831** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L927** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L1473** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L2019** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L2443** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L2472** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L2748** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization


### venv/lib/python3.13/site-packages/sklearn/metrics/tests/test_score_objects.py

🟢 **L1445** [已废弃]: remove when enable_metadata_routing is deprecated


### venv/lib/python3.13/site-packages/sklearn/metrics/_plot/tests/test_common_curve_display.py

🟢 **L263** [已废弃]: Clean-up once `estimator_name` deprecated in all displays

🟢 **L308** [已废弃]: Clean-up once `estimator_name` deprecated in all displays


### venv/lib/python3.13/site-packages/sklearn/ensemble/tests/test_forest.py

🟢 **L161** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L1835** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization

🟢 **L1879** [已废弃]: (1.11): remove the deprecated friedman_mse criterion parametrization


### venv/lib/python3.13/site-packages/sklearn/linear_model/tests/test_logistic.py

🟢 **L434** [已废弃]: (1.12): remove deprecated use_legacy_attributes

🟢 **L658** [已废弃]: (1.12): remove deprecated use_legacy_attributes

🟢 **L2662** [已废弃]: (1.10): use_legacy_attributes gets deprecated

🟢 **L2701** [已废弃]: (1.10): remove this test when n_jobs gets removed

🟢 **L2843** [已废弃]: (1.10): remove when penalty is removed


### venv/lib/python3.13/site-packages/sklearn/utils/tests/test_plotting.py

🟢 **L199** [已废弃]: Remove once kwargs deprecated on all displays


### venv/lib/python3.13/site-packages/sklearn/preprocessing/tests/test_discretization.py

🟢 **L531** [已废弃]: this check is redundant with common checks and can be removed


### venv/lib/python3.13/site-packages/tensorboard/backend/event_processing/event_file_loader.py

🟢 **L80** [已废弃]: (#1711): Find non-deprecated replacement for tf_record_iterator.


### venv/lib/python3.13/site-packages/setuptools/config/_apply_pyprojecttoml.py

🟢 **L352** [已废弃]: remove check when `bdist_wheel` has been fully removed from pypa/wheel


### venv/lib/python3.13/site-packages/setuptools/tests/test_editable_install.py

🟢 **L1097** [已废弃]: Remove tests after _run_build_steps is removed.


### venv/lib/python3.13/site-packages/pydantic/_internal/_generate_schema.py

🟢 **L2559** [已废弃]: V3: this function is only used for deprecated decorators. It should


### venv/lib/python3.13/site-packages/pydantic/_internal/_decorators.py

🟢 **L263** [已废弃]: most likely this branch can be removed when we drop support for Python 3.12:


### venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_estimating_equations.py

🟢 **L1946** [已废弃]: alias to be removed, temporary backwards compatibility

🟢 **L2305** [已废弃]: alias to be removed, temporary backwards compatibility


### venv/lib/python3.13/site-packages/statsmodels/gam/tests/test_gam.py

🟢 **L529** [已废弃]: Mean has to be removed

🟢 **L535** [已废弃]: Mean has to be removed


### venv/lib/python3.13/site-packages/statsmodels/genmod/families/links.py

🟢 **L1292** [已废弃]: Deprecated aliases, remove after 0.15


### venv/lib/python3.13/site-packages/scipy/sparse/_construct.py

🟢 **L670** [已废弃]: delete next 15 lines [combine with _eye()] once spmatrix removed

🟢 **L816** [已废弃]: delete this if-clause and replace _sparse with _array when spmatrix removed

🟢 **L960** [已废弃]: delete this if-clause and replace _sparse with _array when spmatrix removed

🟢 **L1035** [已废弃]: remove this if-structure when sparse matrices removed


### venv/lib/python3.13/site-packages/scipy/integrate/_ivp/bdf.py

🟢 **L289** [已废弃]: switch to csc_array after spmatrix is removed


### venv/lib/python3.13/site-packages/scipy/integrate/_ivp/radau.py

🟢 **L328** [已废弃]: use I = eye_array(self.n, format="csc") after spmatrix removed

🟢 **L379** [已废弃]: Use csc_array after spmatrix removed


### venv/lib/python3.13/site-packages/pandas/core/generic.py

🟢 **L7101** [已废弃]: (3.0): once downcast is removed, we can do the .T


### venv/lib/python3.13/site-packages/pandas/core/series.py

🟢 **L2685** [已废弃]: (3.0): this catching/filtering can be removed

🟢 **L2769** [已废弃]: (3.0): this catching/filtering can be removed

🟢 **L5428** [已废弃]: (3.0): this can be removed once GH#33302 deprecation is enforced


### venv/lib/python3.13/site-packages/pandas/core/frame.py

🟢 **L4057** [已废弃]: (CoW): can be removed if/when we are always Copy-on-Write


### venv/lib/python3.13/site-packages/pandas/core/dtypes/dtypes.py

🟢 **L2271** [已废弃]: (arrow#33642): This can be removed once supported by pyarrow


### venv/lib/python3.13/site-packages/pandas/core/dtypes/common.py

🟢 **L1657** [已废弃]: warnings.catch_warnings can be removed when numpy>2.3.0


### venv/lib/python3.13/site-packages/pandas/core/computation/expr.py

🟢 **L547** [已废弃]: (py314): deprecated since Python 3.8. Remove after Python 3.14 is min

🟢 **L551** [已废弃]: (py314): deprecated since Python 3.8. Remove after Python 3.14 is min

🟢 **L558** [已废弃]: (py314): deprecated since Python 3.8. Remove after Python 3.14 is min


### venv/lib/python3.13/site-packages/pandas/core/arrays/base.py

🟢 **L2170** [已废弃]: (3.0): this can be removed once GH#33302 deprecation is enforced


### venv/lib/python3.13/site-packages/pandas/core/indexes/base.py

🟢 **L4227** [已废弃]: (GH#50617): once Series.__[gs]etitem__ is removed we should be able


### venv/lib/python3.13/site-packages/pandas/tests/copy_view/test_astype.py

🟢 **L137** [已废弃]: (infer_string) this test can be removed after 3.0 (once str is the default)


### venv/lib/python3.13/site-packages/pandas/tests/plotting/test_series.py

🟢 **L983** [已废弃]: (3.0): this can be removed once Period[B] deprecation is enforced


### venv/lib/python3.13/site-packages/pandas/tests/plotting/frame/test_frame.py

🟢 **L2604** [已废弃]: (3.0): this can be removed once Period[B] deprecation is enforced


### venv/lib/python3.13/site-packages/pandas/tests/indexes/period/test_indexing.py

🟢 **L720** [已废弃]: this test used to test get_value, which is removed in 2.0.


### venv/lib/python3.13/site-packages/torch/__init__.py

🟢 **L2219** [文档完善]: Once the undocumented FC window is passed, remove the line below


### venv/lib/python3.13/site-packages/pluggy/_hooks.py

🟢 **L411** [文档完善]: Document, or make private.

🟢 **L417** [文档完善]: Document, or make private.

🟢 **L421** [文档完善]: Document, or make private.


### venv/lib/python3.13/site-packages/networkx/algorithms/cuts.py

🟢 **L19** [文档完善]: STILL NEED TO UPDATE ALL THE DOCUMENTATION!


### venv/lib/python3.13/site-packages/networkx/algorithms/traversal/beamsearch.py

🟢 **L77** [文档完善]: The Python documentation states that for small values, it


### venv/lib/python3.13/site-packages/seaborn/_core/properties.py

🟢 **L800** [文档完善]: Users do not interact directly with properties, so how to document them?


### venv/lib/python3.13/site-packages/google/protobuf/message.py

🟢 **L43** [文档完善]: Link to an HTML document here.

🟢 **L45** [文档完善]: Document that instances of this class will also

🟢 **L49** [文档完善]: Document these fields and methods.

🟢 **L217** [文档完善]: Document handling of unknown fields.

🟢 **L269** [文档完善]: Be sure to document (and test) exactly


### venv/lib/python3.13/site-packages/fontTools/varLib/__init__.py

🟢 **L950** [文档完善]: remove this and always assume 'designspace' is a DesignSpaceDocument,


### venv/lib/python3.13/site-packages/mlflow/store/_unity_catalog/registry/uc_oss_rest_store.py

🟢 **L123** [文档完善]: Update the above reference to UC OSS documentation when it's available


### venv/lib/python3.13/site-packages/torch/_prims_common/__init__.py

🟢 **L1588** [文档完善]: document type promotion kinds


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_utils.py

🟢 **L5422** [文档完善]: improve load_tests() documentation here

🟢 **L5455** [文档完善]: document this and move it to test_serialization


### venv/lib/python3.13/site-packages/torch/testing/_internal/common_quantized.py

🟢 **L276** [文档完善]: document this better


### venv/lib/python3.13/site-packages/torch/ao/quantization/fx/match_utils.py

🟢 **L142** [文档完善]: 1. merge with fuse matcher 2. document the code


### venv/lib/python3.13/site-packages/sqlalchemy/orm/loading.py

🟢 **L385** [文档完善]: need test coverage and documentation for the FrozenResult


### venv/lib/python3.13/site-packages/statsmodels/genmod/generalized_estimating_equations.py

🟢 **L2447** [文档完善]: document or delete

🟢 **L2834** [文档完善]: document or delete


### venv/lib/python3.13/site-packages/statsmodels/discrete/tests/test_sandwich_cov.py

🟢 **L81** [文档完善]: document why we adjust by k_params for some classes


### venv/lib/python3.13/site-packages/statsmodels/tsa/tests/results/results_arima.py

🟢 **L435** [文档完善]: Document source for these non-used results


### venv/lib/python3.13/site-packages/lxml/html/__init__.py

🟢 **L785** [文档完善]: removing the reference to the parent artificial document


### venv/lib/python3.13/site-packages/lxml/html/diff.py

🟢 **L191** [文档完善]: this should take parsed documents too, and use their body


### venv/lib/python3.13/site-packages/pandas/core/dtypes/dtypes.py

🟢 **L209** [文档完善]: Document public vs. private API


### venv/lib/python3.13/site-packages/pandas/core/arrays/arrow/array.py

🟢 **L884** [文档完善]: is this documented somewhere?

