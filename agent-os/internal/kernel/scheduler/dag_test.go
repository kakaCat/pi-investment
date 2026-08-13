package scheduler

import (
	"testing"

	"github.com/google/uuid"
)

func TestDAG_AddTask(t *testing.T) {
	dag := NewDAG()
	taskID := uuid.New()

	dag.AddTask(taskID)

	if _, exists := dag.dependencies[taskID]; !exists {
		t.Error("Task not added to dependencies map")
	}
	if _, exists := dag.dependents[taskID]; !exists {
		t.Error("Task not added to dependents map")
	}
}

func TestDAG_AddDependency(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()

	err := dag.AddDependency(task1, task2)
	if err != nil {
		t.Errorf("Failed to add dependency: %v", err)
	}

	deps := dag.GetDependencies(task1)
	if len(deps) != 1 || deps[0] != task2 {
		t.Error("Dependency not added correctly")
	}

	dependents := dag.GetDependents(task2)
	if len(dependents) != 1 || dependents[0] != task1 {
		t.Error("Dependent not added correctly")
	}
}

func TestDAG_CircularDependency(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()
	task3 := uuid.New()

	// Create chain: task1 -> task2 -> task3
	dag.AddDependency(task1, task2)
	dag.AddDependency(task2, task3)

	// Try to create cycle: task3 -> task1
	err := dag.AddDependency(task3, task1)
	if err == nil {
		t.Error("Expected error for circular dependency, got nil")
	}
}

func TestDAG_HasPath(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()
	task3 := uuid.New()

	// Create chain: task1 -> task2 -> task3
	dag.AddDependency(task1, task2)
	dag.AddDependency(task2, task3)

	// Test path existence
	if !dag.HasPath(task1, task3) {
		t.Error("Expected path from task1 to task3")
	}

	if dag.HasPath(task3, task1) {
		t.Error("Should not have path from task3 to task1")
	}
}

func TestDAG_TopologicalSort(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()
	task3 := uuid.New()

	// Create dependencies: task2 -> task1, task3 -> task1, task3 -> task2
	dag.AddDependency(task2, task1)
	dag.AddDependency(task3, task1)
	dag.AddDependency(task3, task2)

	sorted, err := dag.TopologicalSort()
	if err != nil {
		t.Errorf("Topological sort failed: %v", err)
	}

	if len(sorted) != 3 {
		t.Errorf("Expected 3 tasks, got %d", len(sorted))
	}

	// Verify order: task1 should come before task2 and task3
	// task2 should come before task3
	positions := make(map[uuid.UUID]int)
	for i, id := range sorted {
		positions[id] = i
	}

	if positions[task1] >= positions[task2] {
		t.Error("task1 should come before task2")
	}
	if positions[task1] >= positions[task3] {
		t.Error("task1 should come before task3")
	}
	if positions[task2] >= positions[task3] {
		t.Error("task2 should come before task3")
	}
}

func TestDAG_CanExecute(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()
	task3 := uuid.New()

	// task3 depends on task1 and task2
	dag.AddDependency(task3, task1)
	dag.AddDependency(task3, task2)

	completedTasks := make(map[uuid.UUID]bool)

	// task3 cannot execute if dependencies not completed
	if dag.CanExecute(task3, completedTasks) {
		t.Error("task3 should not be executable without dependencies")
	}

	// Complete task1
	completedTasks[task1] = true
	if dag.CanExecute(task3, completedTasks) {
		t.Error("task3 should not be executable with only one dependency")
	}

	// Complete task2
	completedTasks[task2] = true
	if !dag.CanExecute(task3, completedTasks) {
		t.Error("task3 should be executable with all dependencies")
	}
}

func TestDAG_RemoveDependency(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()

	dag.AddDependency(task1, task2)
	dag.RemoveDependency(task1, task2)

	deps := dag.GetDependencies(task1)
	if len(deps) != 0 {
		t.Error("Dependency should be removed")
	}

	dependents := dag.GetDependents(task2)
	if len(dependents) != 0 {
		t.Error("Dependent should be removed")
	}
}

func TestDAG_GetExecutionOrder(t *testing.T) {
	dag := NewDAG()
	task1 := uuid.New()
	task2 := uuid.New()
	task3 := uuid.New()
	task4 := uuid.New()

	// Create dependencies:
	// task2 -> task1
	// task3 -> task1
	// task4 -> task2, task3
	dag.AddDependency(task2, task1)
	dag.AddDependency(task3, task1)
	dag.AddDependency(task4, task2)
	dag.AddDependency(task4, task3)

	// Get execution order for task4 (should include all dependencies)
	order, err := dag.GetExecutionOrder([]uuid.UUID{task4})
	if err != nil {
		t.Errorf("GetExecutionOrder failed: %v", err)
	}

	if len(order) != 4 {
		t.Errorf("Expected 4 tasks in execution order, got %d", len(order))
	}

	// Verify task1 comes first
	if order[0] != task1 {
		t.Error("task1 should be first in execution order")
	}

	// Verify task4 comes last
	if order[len(order)-1] != task4 {
		t.Error("task4 should be last in execution order")
	}
}
