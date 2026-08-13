package scheduler

import (
	"fmt"

	"github.com/google/uuid"
)

// DAG represents a directed acyclic graph of task dependencies
type DAG struct {
	// adjacency list: taskID -> list of tasks it depends on
	dependencies map[uuid.UUID][]uuid.UUID
	// reverse adjacency list: taskID -> list of tasks that depend on it
	dependents map[uuid.UUID][]uuid.UUID
}

// NewDAG creates a new DAG
func NewDAG() *DAG {
	return &DAG{
		dependencies: make(map[uuid.UUID][]uuid.UUID),
		dependents:   make(map[uuid.UUID][]uuid.UUID),
	}
}

// AddTask adds a task to the DAG
func (d *DAG) AddTask(taskID uuid.UUID) {
	if _, exists := d.dependencies[taskID]; !exists {
		d.dependencies[taskID] = []uuid.UUID{}
	}
	if _, exists := d.dependents[taskID]; !exists {
		d.dependents[taskID] = []uuid.UUID{}
	}
}

// AddDependency adds a dependency: taskID depends on dependsOnTaskID
func (d *DAG) AddDependency(taskID, dependsOnTaskID uuid.UUID) error {
	// Ensure both tasks exist in the DAG
	d.AddTask(taskID)
	d.AddTask(dependsOnTaskID)

	// Check for circular dependency before adding
	if d.HasPath(dependsOnTaskID, taskID) {
		return fmt.Errorf("circular dependency detected: adding dependency from %s to %s would create a cycle", taskID, dependsOnTaskID)
	}

	// Add to dependencies
	if !contains(d.dependencies[taskID], dependsOnTaskID) {
		d.dependencies[taskID] = append(d.dependencies[taskID], dependsOnTaskID)
	}

	// Add to dependents (reverse edge)
	if !contains(d.dependents[dependsOnTaskID], taskID) {
		d.dependents[dependsOnTaskID] = append(d.dependents[dependsOnTaskID], taskID)
	}

	return nil
}

// RemoveDependency removes a dependency
func (d *DAG) RemoveDependency(taskID, dependsOnTaskID uuid.UUID) {
	d.dependencies[taskID] = removeUUID(d.dependencies[taskID], dependsOnTaskID)
	d.dependents[dependsOnTaskID] = removeUUID(d.dependents[dependsOnTaskID], taskID)
}

// GetDependencies returns all tasks that the given task depends on
func (d *DAG) GetDependencies(taskID uuid.UUID) []uuid.UUID {
	return d.dependencies[taskID]
}

// GetDependents returns all tasks that depend on the given task
func (d *DAG) GetDependents(taskID uuid.UUID) []uuid.UUID {
	return d.dependents[taskID]
}

// HasPath checks if there's a path from start to end using DFS
func (d *DAG) HasPath(start, end uuid.UUID) bool {
	if start == end {
		return true
	}

	visited := make(map[uuid.UUID]bool)
	return d.dfs(start, end, visited)
}

// dfs performs depth-first search to find a path
func (d *DAG) dfs(current, target uuid.UUID, visited map[uuid.UUID]bool) bool {
	if current == target {
		return true
	}

	visited[current] = true

	// Follow dependencies (tasks this task depends on)
	for _, dep := range d.dependencies[current] {
		if !visited[dep] {
			if d.dfs(dep, target, visited) {
				return true
			}
		}
	}

	return false
}

// TopologicalSort performs a topological sort of all tasks
// Returns tasks in order such that all dependencies come before dependents
func (d *DAG) TopologicalSort() ([]uuid.UUID, error) {
	// Calculate in-degree for each node (number of dependencies each task has)
	inDegree := make(map[uuid.UUID]int)

	// Initialize all nodes with 0 in-degree
	for taskID := range d.dependencies {
		if _, exists := inDegree[taskID]; !exists {
			inDegree[taskID] = 0
		}
	}

	// Count in-degrees (number of tasks each task depends on)
	for taskID, deps := range d.dependencies {
		inDegree[taskID] = len(deps)
	}

	// Queue for tasks with no dependencies (in-degree 0)
	queue := []uuid.UUID{}
	for taskID, degree := range inDegree {
		if degree == 0 {
			queue = append(queue, taskID)
		}
	}

	// Process queue
	var result []uuid.UUID
	for len(queue) > 0 {
		// Dequeue
		current := queue[0]
		queue = queue[1:]
		result = append(result, current)

		// For each task that depends on current task
		for _, dependent := range d.dependents[current] {
			inDegree[dependent]--
			if inDegree[dependent] == 0 {
				queue = append(queue, dependent)
			}
		}
	}

	// If we processed all nodes, there's no cycle
	if len(result) != len(d.dependencies) {
		return nil, fmt.Errorf("circular dependency detected in DAG")
	}

	return result, nil
}

// GetExecutionOrder returns tasks in the order they should be executed
// considering their dependencies
func (d *DAG) GetExecutionOrder(taskIDs []uuid.UUID) ([]uuid.UUID, error) {
	// Build a sub-DAG with only the requested tasks and their dependencies
	subDAG := NewDAG()
	visited := make(map[uuid.UUID]bool)

	// Add tasks and their dependencies recursively
	var addWithDeps func(uuid.UUID)
	addWithDeps = func(taskID uuid.UUID) {
		if visited[taskID] {
			return
		}
		visited[taskID] = true
		subDAG.AddTask(taskID)

		for _, dep := range d.GetDependencies(taskID) {
			addWithDeps(dep)
			subDAG.AddDependency(taskID, dep)
		}
	}

	for _, taskID := range taskIDs {
		addWithDeps(taskID)
	}

	// Return topological sort of sub-DAG
	return subDAG.TopologicalSort()
}

// CanExecute checks if a task can be executed based on its dependencies
// A task can execute if all its dependencies have completed successfully
func (d *DAG) CanExecute(taskID uuid.UUID, completedTasks map[uuid.UUID]bool) bool {
	deps := d.GetDependencies(taskID)
	if len(deps) == 0 {
		return true // No dependencies
	}

	for _, dep := range deps {
		if !completedTasks[dep] {
			return false // Dependency not completed
		}
	}

	return true
}

// Helper functions

func contains(slice []uuid.UUID, item uuid.UUID) bool {
	for _, v := range slice {
		if v == item {
			return true
		}
	}
	return false
}

func removeUUID(slice []uuid.UUID, item uuid.UUID) []uuid.UUID {
	result := []uuid.UUID{}
	for _, v := range slice {
		if v != item {
			result = append(result, v)
		}
	}
	return result
}
